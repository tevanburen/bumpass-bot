from bumpass_bot import db


def main():
    with db.connect() as connection:
        for chat_id, name, participants in db.list_group_chats(connection):
            print(f"{chat_id}\t{participants}\t{name or '(unnamed)'}")


if __name__ == "__main__":
    main()
