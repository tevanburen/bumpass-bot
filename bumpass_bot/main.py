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
    # When we started waiting on the current message's attachments to download.
    waiting_since: float | None = None


def format_quote(quote, name_resolver):
    """One line showing the message a reply points at."""
    snippet = " ".join(quote.text.split()) or "[attachment]"
    if len(snippet) > QUOTE_MAX_CHARS:
        snippet = snippet[:QUOTE_MAX_CHARS].rstrip() + "…"

    # A quote of our own account's message has no author, and when that message
    # was itself forwarded by the bot its text already starts with the original sender.
    if quote.sender is None:
        line = f'↪ "{snippet}"'
    else:
        line = f'↪ "{name_resolver.lookup(quote.sender)}: {snippet}"'

    return line.translate(ITALIC_TABLE)


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
    chat_a = Chat(chat_a_id, db.get_chat_guid(connection, chat_a_id), baseline)
    chat_b = Chat(chat_b_id, db.get_chat_guid(connection, chat_b_id), baseline)

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
            try:
                forward_new_messages(
                    connection, source, destination, sent_tracker, name_resolver
                )
            except Exception as error:
                print(f"Error fetching messages, will retry next poll: {error}")


if __name__ == "__main__":
    main()
