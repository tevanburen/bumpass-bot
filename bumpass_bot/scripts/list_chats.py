"""Prints the chat_identifier, member count and name of every group chat, for setting up .env.

Usage: uv run python -m bumpass_bot.scripts.list_chats
"""

from bumpass_bot import db


def main():
    with db.connect() as connection:
        for chat_id, name, participants in db.list_group_chats(connection):
            print(f"{chat_id}\t{participants}\t{name or '(unnamed)'}")


if __name__ == "__main__":
    main()
