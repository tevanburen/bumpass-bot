import time
from dataclasses import dataclass
from string import ascii_lowercase, ascii_uppercase

from bumpass_bot import config, db
from bumpass_bot.names import NameResolver
from bumpass_bot.send import send_file, send_message
from bumpass_bot.sent_tracker import SentTracker


QUOTE_MAX_CHARS = 60

# Messages can't send formatted text through AppleScript, so italics are the
# Mathematical Sans-Serif Italic letters. Digits, punctuation and non-ASCII letters have none.
ITALIC_TABLE = {
    **{ord(letter): chr(0x1D608 + index) for index, letter in enumerate(ascii_uppercase)},
    **{ord(letter): chr(0x1D622 + index) for index, letter in enumerate(ascii_lowercase)},
}


@dataclass
class Chat:
    id: str
    guid: str
    last_rowid: int
    # Edits are only forwarded for messages from after startup, which are the ones we forwarded.
    start_rowid: int
    # The newest date_edited we've handled.
    last_edit: int
    # When we started waiting on the current message's attachments to download.
    waiting_since: float | None = None


def shorten(text):
    # Drop a quote line of its own, which is there when the text was a reply the bot forwarded.
    own_lines = (line for line in text.splitlines() if not line.startswith("↪"))
    snippet = " ".join(" ".join(own_lines).split()) or "[attachment]"
    if len(snippet) > QUOTE_MAX_CHARS:
        snippet = snippet[:QUOTE_MAX_CHARS].rstrip() + "…"

    return snippet


def format_quote(quote, name_resolver):
    """One line showing the message a reply points at."""
    snippet = shorten(quote.text)

    # A quote of our own account's message has no author, and when that message
    # was itself forwarded by the bot its text already starts with the original sender.
    if quote.sender is None:
        line = f'↪ "{snippet}"'
    else:
        line = f'↪ "{name_resolver.lookup(quote.sender)}: {snippet}"'

    return line.translate(ITALIC_TABLE)


def is_forwarded_reaction(quote):
    """Whether the quoted message is a reaction the bot forwarded as text."""
    lines = quote.text.splitlines()
    return (
        len(lines) > 1
        and lines[-1].startswith("reacted ")
        and any(line.startswith("↪") for line in lines)
    )


def format_forward(message, text, has_attachments, name_resolver):
    """Text to send ahead of any files, or "" if there is none."""
    if not text and not has_attachments:
        return ""

    lines = []
    # Own messages are forwarded without a header.
    if not message.is_from_me:
        lines.append(f"{name_resolver.lookup(message.sender)}:")

    if message.reply_to:
        lines.append(format_quote(message.reply_to, name_resolver))

    if text:
        lines.append(text)

    return "\n".join(lines)


def format_edit(edit, name_resolver):
    lines = []
    # Own messages are forwarded without a header.
    if not edit.is_from_me:
        lines.append(f"{name_resolver.lookup(edit.sender)} edited:")

    if edit.previous_text:
        lines.append(f'↪ "was: {shorten(edit.previous_text)}"'.translate(ITALIC_TABLE))

    lines.append(edit.text)
    return "\n".join(lines)


def forward_edits(connection, source, destination, sent_tracker, name_resolver):
    # A message already sent can't be edited through AppleScript, so an edit goes out as a new one.
    edits = db.get_new_edits(connection, source.id, source.last_edit, source.start_rowid)

    for edit in edits:
        source.last_edit = edit.edited_at

        # Not forwarded yet, so it goes out with its edited text as a normal message.
        if edit.rowid > source.last_rowid or not edit.text:
            continue

        forwarded_text = format_edit(edit, name_resolver)
        print(f"[{source.id} {edit.rowid}] edit {forwarded_text!r}")

        try:
            send_message(destination.guid, forwarded_text)
            sent_tracker.record(destination.id, forwarded_text)
        except Exception as error:
            print(f"Error sending edit of message {edit.rowid}: {error}")


def forward_new_messages(connection, source, destination, sent_tracker, name_resolver):
    messages = db.get_new_messages(connection, source.id, source.last_rowid)

    for message in messages:
        if message.attachments_pending:
            if source.waiting_since is None:
                source.waiting_since = time.monotonic()

            if time.monotonic() - source.waiting_since < config.ATTACHMENT_WAIT_SECONDS:
                # Leave the watermark alone and retry this message next poll.
                return

            print(f"[{source.id} {message.rowid}] Attachment never finished downloading, skipping it")

        source.waiting_since = None

        # Advance first so a failed send is logged and skipped, not retried into duplicates.
        source.last_rowid = message.rowid

        # Messages the bot sent into this chat (forwarded from the other one)
        # come back as is_from_me; skip them so they don't bounce back.
        text = message.text
        attachments = message.attachments
        if message.is_from_me:
            if text and sent_tracker.consume(source.id, text):
                text = ""
            attachments = tuple(
                attachment
                for attachment in attachments
                if not sent_tracker.consume_file(source.id, attachment)
            )

        if message.reaction:
            # Without the message that was reacted to, "reacted 😂" says nothing.
            if not message.reply_to or is_forwarded_reaction(message.reply_to):
                continue

            text = f"reacted {message.reaction}"

        if not text and not attachments:
            continue

        forwarded_text = format_forward(message, text, bool(attachments), name_resolver)
        file_names = ", ".join(attachment.path for attachment in attachments)
        print(f"[{source.id} {message.rowid}] {forwarded_text!r} files=[{file_names}]")

        if forwarded_text:
            try:
                send_message(destination.guid, forwarded_text)
                sent_tracker.record(destination.id, forwarded_text)
            except Exception as error:
                print(f"Error sending message {message.rowid}: {error}")

        for attachment in attachments:
            try:
                send_file(destination.guid, attachment.path)
                sent_tracker.record_file(destination.id, attachment)
            except Exception as error:
                print(f"Error sending attachment of message {message.rowid}: {error}")


def main():
    chat_a_id, chat_b_id = config.get_chat_ids()

    connection = db.connect()

    # Baseline so we only react to messages that arrive after startup.
    baseline = db.get_max_rowid(connection)
    last_edit = db.get_max_date_edited(connection)
    chat_a = Chat(chat_a_id, db.get_chat_guid(connection, chat_a_id), baseline, baseline, last_edit)
    chat_b = Chat(chat_b_id, db.get_chat_guid(connection, chat_b_id), baseline, baseline, last_edit)

    directions = [(chat_a, chat_b)]
    if not config.ONE_WAY:
        directions.append((chat_b, chat_a))

    arrow = "->" if config.ONE_WAY else "<->"
    print(
        f"Forwarding {chat_a.id} {arrow} {chat_b.id}, "
        f"existing history ignored up to ROWID {baseline}"
    )

    sent_tracker = SentTracker()
    name_resolver = NameResolver()

    while True:
        time.sleep(config.POLL_SECONDS)

        for source, destination in directions:
            # Edits go first so one to a message we haven't forwarded yet is left to the normal path.
            if config.EDITS:
                try:
                    forward_edits(connection, source, destination, sent_tracker, name_resolver)
                except Exception as error:
                    print(f"Error fetching edits, will retry next poll: {error}")

            try:
                forward_new_messages(
                    connection, source, destination, sent_tracker, name_resolver
                )
            except Exception as error:
                print(f"Error fetching messages, will retry next poll: {error}")


if __name__ == "__main__":
    main()
