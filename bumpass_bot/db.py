import sqlite3
from dataclasses import dataclass

from bumpass_bot import config

# Tapbacks/reactions are stored as messages with a non-zero associated_message_type.
NEW_MESSAGES_QUERY = """
    SELECT m.ROWID, m.text, m.attributedBody, m.is_from_me, m.cache_has_attachments, h.id
    FROM message m
    JOIN chat_message_join cmj ON cmj.message_id = m.ROWID
    JOIN chat c ON c.ROWID = cmj.chat_id
    LEFT JOIN handle h ON h.ROWID = m.handle_id
    WHERE c.chat_identifier = ?
      AND m.ROWID > ?
      AND m.associated_message_type = 0
    ORDER BY m.ROWID
"""

LIST_GROUP_CHATS_QUERY = """
    SELECT c.chat_identifier, c.display_name, COUNT(chj.handle_id)
    FROM chat c
    LEFT JOIN chat_handle_join chj ON chj.chat_id = c.ROWID
    WHERE c.style = 43
    GROUP BY c.ROWID
    ORDER BY c.display_name
"""


@dataclass(frozen=True)
class Message:
    rowid: int
    sender: str | None
    text: str
    is_from_me: bool
    has_attachments: bool


def connect():
    # Read-only so we can never corrupt Messages' database.
    return sqlite3.connect(f"file:{config.DB_PATH}?mode=ro", uri=True)


def decode_attributed_body(blob):
    """Extract the plain text from a typedstream NSAttributedString blob.

    Newer macOS versions leave message.text NULL and only fill attributedBody.
    """
    marker = blob.find(b"NSString")
    if marker == -1:
        return None

    # Skip the marker plus 5 bytes of class metadata, then read the length prefix.
    pos = marker + len(b"NSString") + 5
    length = blob[pos]
    pos += 1
    if length == 0x81:
        length = int.from_bytes(blob[pos : pos + 2], "little")
        pos += 2
    elif length == 0x82:
        length = int.from_bytes(blob[pos : pos + 4], "little")
        pos += 4

    return blob[pos : pos + length].decode("utf-8", errors="replace")


def get_max_rowid(connection):
    return connection.execute("SELECT COALESCE(MAX(ROWID), 0) FROM message").fetchone()[0]


def get_new_messages(connection, chat_id, after_rowid):
    messages = []
    for rowid, text, body, is_from_me, has_attachments, sender in connection.execute(
        NEW_MESSAGES_QUERY, (chat_id, after_rowid)
    ):
        if text is None and body is not None:
            text = decode_attributed_body(body)

        messages.append(
            Message(
                rowid=rowid,
                sender=sender,
                # U+FFFC is the placeholder for an attachment embedded in the text.
                text=(text or "").replace("￼", "").strip(),
                is_from_me=bool(is_from_me),
                has_attachments=bool(has_attachments),
            )
        )

    return messages


def get_chat_guid(connection, chat_id):
    row = connection.execute(
        "SELECT guid FROM chat WHERE chat_identifier = ?", (chat_id,)
    ).fetchone()
    if row is None:
        raise ValueError(f"No chat found with identifier {chat_id}")

    return row[0]


def list_group_chats(connection):
    return connection.execute(LIST_GROUP_CHATS_QUERY).fetchall()
