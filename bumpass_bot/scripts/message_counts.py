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
    # Keyed by contact, so someone who has used several numbers or emails is one row.
    totals = Counter()
    # contact -> names of the chats they're a member of now
    memberships = {}
    display_names = {}

    with db.connect() as connection:
        chat_ids = config.get_chat_ids()
        chat_names = [db.get_chat_name(connection, chat_id) or chat_id for chat_id in chat_ids]

        for chat_id, chat_name in zip(chat_ids, chat_names, strict=True):
            for handle, count in db.get_message_counts(connection, chat_id, since).items():
                contact = names.contact_id(handle)
                display_names[contact] = names.lookup(handle)
                totals[contact] += count

            for handle in db.get_chat_members(connection, chat_id):
                contact = names.contact_id(handle)
                display_names[contact] = names.lookup(handle)
                memberships.setdefault(contact, set()).add(chat_name)

    def chats_label(contact):
        chats = memberships.get(contact, set())
        if len(chats) == len(chat_ids):
            return "both"

        # Someone who posted in the window but has since left both chats.
        return next(iter(chats)) if chats else "neither"

    # Members who haven't said anything still get a row, with 0.
    rows = sorted(
        (
            (name, totals[contact], chats_label(contact))
            for contact, name in display_names.items()
        ),
        key=lambda row: (-row[1], row[0].casefold()),
    )

    # Ties share a rank and the next rank skips ahead (1, 2, 2, 4).
    ranked = [
        (1 + sum(1 for other in rows if other[1] > count), name, count, chats)
        for name, count, chats in rows
    ]

    print(f"Messages in the last {DAYS} days in {' and '.join(chat_names)}, not counting the bot:\n")
    print_table(("Rank", "Name", "Count", "Chat"), ranked)


if __name__ == "__main__":
    main()
