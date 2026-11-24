"""Prints how many messages each person sent in each chat from .env over the last 30 days.

Usage: uv run python -m bumpass_bot.scripts.message_counts
"""

import time

from bumpass_bot import config, db
from bumpass_bot.names import NameResolver

DAYS = 30


def print_counts(connection, names, chat_id, since):
    counts = db.get_message_counts(connection, chat_id, since)
    # Members who haven't said anything still get a row, with 0.
    for handle in db.get_chat_members(connection, chat_id):
        counts.setdefault(handle, 0)

    rows = sorted(
        ((names.lookup(handle), count) for handle, count in counts.items()),
        key=lambda row: (-row[1], row[0].casefold()),
    )

    chat_name = db.get_chat_name(connection, chat_id) or chat_id
    print(f"{chat_name}, messages in the last {DAYS} days (not counting the bot):")
    for name, count in rows:
        print(f"{count:6}  {name}")


def main():
    since = time.time() - DAYS * 86400
    names = NameResolver()

    with db.connect() as connection:
        for index, chat_id in enumerate(config.get_chat_ids()):
            if index:
                print()
            print_counts(connection, names, chat_id, since)


if __name__ == "__main__":
    main()
