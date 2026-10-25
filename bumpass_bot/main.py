import time
from dataclasses import dataclass

from bumpass_bot import config, db
from bumpass_bot.names import NameResolver
from bumpass_bot.send import send_file, send_message
from bumpass_bot.sent_tracker import SentTracker


@dataclass
class Chat:
    id: str
    guid: str
    last_rowid: int
    # When we started waiting on the current message's attachments to download.
    waiting_since: float | None = None


def format_forward(message, text, has_attachments, name_resolver):
    """Text to send ahead of any files, or "" if there is none."""
    # Own messages are forwarded without a header.
    if message.is_from_me:
        return text

    sender = name_resolver.lookup(message.sender)
    if text:
        return f"{sender}:\n{text}"

    return f"{sender}:" if has_attachments else ""


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

    print(
        f"Forwarding {chat_a.id} <-> {chat_b.id}, "
        f"existing history ignored up to ROWID {baseline}"
    )

    sent_tracker = SentTracker()
    name_resolver = NameResolver()

    while True:
        time.sleep(config.POLL_SECONDS)

        for source, destination in ((chat_a, chat_b), (chat_b, chat_a)):
            try:
                forward_new_messages(
                    connection, source, destination, sent_tracker, name_resolver
                )
            except Exception as error:
                print(f"Error fetching messages, will retry next poll: {error}")


if __name__ == "__main__":
    main()
