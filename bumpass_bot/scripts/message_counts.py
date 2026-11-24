"""Prints how many messages each person sent in a chat over the last 30 days.

Usage: uv run python -m bumpass_bot.scripts.message_counts <chat_id>
"""

import sys
import time

from bumpass_bot import db
from bumpass_bot.names import NameResolver

DAYS = 30


def main():
    if len(sys.argv) != 2:
        sys.exit("Usage: uv run python -m bumpass_bot.scripts.message_counts <chat_id>")

    chat_id = sys.argv[1]
    with db.connect() as connection:
        try:
            db.get_chat_guid(connection, chat_id)
        except ValueError as error:
            sys.exit(str(error))

        counts = db.get_message_counts(connection, chat_id, time.time() - DAYS * 86400)
        # Members who haven't said anything still get a row, with 0.
        for handle in db.get_chat_members(connection, chat_id):
            counts.setdefault(handle, 0)

        chat_name = db.get_chat_name(connection, chat_id) or chat_id

    names = NameResolver()
    rows = sorted(
        ((names.lookup(handle), count) for handle, count in counts.items()),
        key=lambda row: (-row[1], row[0].casefold()),
    )

    print(f"{chat_name}, messages in the last {DAYS} days (not counting the bot):")
    for name, count in rows:
        print(f"{count:6}  {name}")


if __name__ == "__main__":
    main()
