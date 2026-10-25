import time

from bumpass_bot import config, db
from bumpass_bot.send import send_message


def format_forward(message):
    sender = config.SELF_NAME if message.is_from_me else message.sender
    return f"{sender}:\n{message.text}"


def main():
    chat_a_id, chat_b_id = config.get_chat_ids()

    connection = db.connect()
    chat_b_guid = db.get_chat_guid(connection, chat_b_id)

    # Baseline so we only react to messages that arrive after startup.
    last_rowid = db.get_max_rowid(connection)
    mode = "DRY RUN" if config.DRY_RUN else "live"
    print(
        f"Forwarding {chat_a_id} -> {chat_b_id} ({mode}), "
        f"existing history ignored up to ROWID {last_rowid}"
    )

    while True:
        time.sleep(config.POLL_SECONDS)

        try:
            messages = db.get_new_messages(connection, chat_a_id, last_rowid)
        except Exception as error:
            print(f"Error fetching messages, will retry next poll: {error}")
            continue

        for message in messages:
            # Advance first so a failed send is logged and skipped, not retried into duplicates.
            last_rowid = message.rowid

            # Text only for now.
            if not message.text:
                continue

            forwarded = format_forward(message)
            print(f"[{message.rowid}] {forwarded}")

            if config.DRY_RUN:
                continue

            try:
                send_message(chat_b_guid, forwarded)
            except Exception as error:
                print(f"Error sending message {message.rowid}: {error}")


if __name__ == "__main__":
    main()
