"""Prints a table of how many messages each person sent across both chats in .env over the
last 30 days, and which of the chats they're in now.

Usage: uv run python -m bumpass_bot.scripts.message_counts
"""

import time
from collections import Counter

from bumpass_bot import config, db
from bumpass_bot.names import NameResolver

DAYS = 30


def print_table(headers, rows):
    widths = [max(len(str(cell)) for cell in column) for column in zip(headers, *rows, strict=True)]
    print(" | ".join(header.ljust(width) for header, width in zip(headers, widths, strict=True)).rstrip())
    print("-+-".join("-" * width for width in widths))
    for row in rows:
        cells = (
            str(cell).rjust(width) if isinstance(cell, int) else cell.ljust(width)
            for cell, width in zip(row, widths, strict=True)
        )
        print(" | ".join(cells).rstrip())


def main():
    since = time.time() - DAYS * 86400
    names = NameResolver()
    totals = Counter()
    # handle -> names of the chats they're a member of now
    memberships = {}

    with db.connect() as connection:
        chat_ids = config.get_chat_ids()
        chat_names = [db.get_chat_name(connection, chat_id) or chat_id for chat_id in chat_ids]

        for chat_id, chat_name in zip(chat_ids, chat_names, strict=True):
            totals.update(db.get_message_counts(connection, chat_id, since))
            for handle in db.get_chat_members(connection, chat_id):
                memberships.setdefault(handle, []).append(chat_name)

    def chats_label(handle):
        chats = memberships.get(handle, [])
        if len(chats) == len(chat_ids):
            return "both"

        # Someone who posted in the window but has since left both chats.
        return chats[0] if chats else "neither"

    # Members who haven't said anything still get a row, with 0.
    handles = set(totals) | set(memberships)
    rows = sorted(
        ((names.lookup(handle), totals[handle], chats_label(handle)) for handle in handles),
        key=lambda row: (-row[1], row[0].casefold()),
    )

    print(f"Messages in the last {DAYS} days in {' and '.join(chat_names)}, not counting the bot:\n")
    print_table(("Name", "Count", "Chat"), rows)


if __name__ == "__main__":
    main()
