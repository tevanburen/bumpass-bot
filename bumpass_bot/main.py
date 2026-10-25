import time
from dataclasses import dataclass

from bumpass_bot import config, db
from bumpass_bot.send import send_message
from bumpass_bot.sent_tracker import SentTracker


@dataclass
class Chat:
    id: str
    guid: str
    last_rowid: int


def format_forward(message):
    sender = config.SELF_NAME if message.is_from_me else message.sender
    return f"{sender}:\n{message.text}"


def forward_new_messages(connection, source, destination, sent_tracker):
    messages = db.get_new_messages(connection, source.id, source.last_rowid)

    for message in messages:
        # Advance first so a failed send is logged and skipped, not retried into duplicates.
        source.last_rowid = message.rowid

        # Text only for now.
        if not message.text:
            continue

        # Messages the bot sent into this chat (forwarded from the other one)
        # come back as is_from_me; skip them so they don't bounce back.
        if message.is_from_me and sent_tracker.consume(source.id, message.text):
            continue

        forwarded = format_forward(message)
        print(f"[{source.id} {message.rowid}] {forwarded}")

        if config.DRY_RUN:
            continue

        try:
            send_message(destination.guid, forwarded)
        except Exception as error:
            print(f"Error sending message {message.rowid}: {error}")
            continue

        sent_tracker.record(destination.id, forwarded)


def main():
    chat_a_id, chat_b_id = config.get_chat_ids()

    connection = db.connect()

    # Baseline so we only react to messages that arrive after startup.
    baseline = db.get_max_rowid(connection)
    chat_a = Chat(chat_a_id, db.get_chat_guid(connection, chat_a_id), baseline)
    chat_b = Chat(chat_b_id, db.get_chat_guid(connection, chat_b_id), baseline)

    mode = "DRY RUN" if config.DRY_RUN else "live"
    print(
        f"Forwarding {chat_a.id} <-> {chat_b.id} ({mode}), "
        f"existing history ignored up to ROWID {baseline}"
    )

    sent_tracker = SentTracker()

    while True:
        time.sleep(config.POLL_SECONDS)

        for source, destination in ((chat_a, chat_b), (chat_b, chat_a)):
            try:
                forward_new_messages(connection, source, destination, sent_tracker)
            except Exception as error:
                print(f"Error fetching messages, will retry next poll: {error}")


if __name__ == "__main__":
    main()
