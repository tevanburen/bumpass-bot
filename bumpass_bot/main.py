import time

from bumpass_bot import config, db


def main():
    chat_a_id, _chat_b_id = config.get_chat_ids()

    connection = db.connect()

    # Baseline so we only react to messages that arrive after startup.
    last_rowid = db.get_max_rowid(connection)
    print(f"Listening on {chat_a_id} (existing history ignored up to ROWID {last_rowid})")

    while True:
        time.sleep(config.POLL_SECONDS)

        try:
            messages = db.get_new_messages(connection, chat_a_id, last_rowid)
        except Exception as error:
            print(f"Error fetching messages, will retry next poll: {error}")
            continue

        for message in messages:
            last_rowid = message.rowid
            sender = "Me" if message.is_from_me else message.sender
            attachment_note = " [attachment]" if message.has_attachments else ""
            print(f"[{message.rowid}] {sender}: {message.text}{attachment_note}")


if __name__ == "__main__":
    main()
