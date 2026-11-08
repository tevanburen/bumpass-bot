import sqlite3
from dataclasses import dataclass
from os.path import exists, expanduser

from bumpass_bot import config

# Tapbacks/reactions are stored as messages with a non-zero associated_message_type.
NEW_MESSAGES_QUERY = """
    SELECT m.ROWID, m.text, m.attributedBody, m.is_from_me, h.id, m.thread_originator_guid
    FROM message m
    JOIN chat_message_join cmj ON cmj.message_id = m.ROWID
    JOIN chat c ON c.ROWID = cmj.chat_id
    LEFT JOIN handle h ON h.ROWID = m.handle_id
    WHERE c.chat_identifier = ?
      AND m.ROWID > ?
      AND m.associated_message_type = 0
    ORDER BY m.ROWID
"""

LATEST_IN_THREAD_QUERY = """
    SELECT m.text, m.attributedBody, m.is_from_me, h.id
    FROM message m
    LEFT JOIN handle h ON h.ROWID = m.handle_id
    WHERE m.ROWID < ?
      AND (m.guid = ? OR m.thread_originator_guid = ?)
    ORDER BY m.ROWID DESC
    LIMIT 1
"""

ATTACHMENTS_QUERY = """
    SELECT a.filename, a.mime_type, a.transfer_state
    FROM attachment a
    JOIN message_attachment_join maj ON maj.attachment_id = a.ROWID
    WHERE maj.message_id = ?
      AND a.is_sticker = 0
      AND a.mime_type IS NOT NULL
    ORDER BY a.ROWID
"""

# attachment.transfer_state value for a finished transfer.
TRANSFER_COMPLETE = 5

LIST_GROUP_CHATS_QUERY = """
    SELECT c.chat_identifier, c.display_name, COUNT(chj.handle_id)
    FROM chat c
    LEFT JOIN chat_handle_join chj ON chj.chat_id = c.ROWID
    WHERE c.style = 43
    GROUP BY c.ROWID
    ORDER BY c.display_name
"""


@dataclass(frozen=True)
class Attachment:
    path: str
    mime_type: str


@dataclass(frozen=True)
class Quote:
    # None when the quoted message was sent from this Mac's account.
    sender: str | None
    text: str


@dataclass(frozen=True)
class Message:
    rowid: int
    sender: str | None
    text: str
    is_from_me: bool
    attachments: tuple[Attachment, ...]
    # True while some attachment hasn't finished downloading to disk.
    attachments_pending: bool
    # The message this one replies to, if it is a reply and the original is still in the database.
    reply_to: Quote | None = None


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


def get_attachments(connection, message_rowid):
    """Return (ready attachments, whether any are still downloading)."""
    ready = []
    pending = False
    for filename, mime_type, transfer_state in connection.execute(
        ATTACHMENTS_QUERY, (message_rowid,)
    ):
        path = expanduser(filename) if filename else None
        if transfer_state == TRANSFER_COMPLETE and path and exists(path):
            ready.append(Attachment(path=path, mime_type=mime_type))
        else:
            pending = True

    return tuple(ready), pending


def read_text(text, body):
    if text is None and body is not None:
        text = decode_attributed_body(body)

    # U+FFFC is the placeholder for an attachment embedded in the text.
    return (text or "").replace("￼", "").strip()


def get_quote(connection, thread_guid, rowid):
    """The latest message in the reply's thread from before the reply.

    The database doesn't record which message of a thread was replied to, only
    the thread's first message (thread_originator_guid). reply_to_guid is no help:
    it is just the previous message in the chat.
    """
    if not thread_guid:
        return None

    # Some references use the form "p:<part>/<guid>".
    root = thread_guid.rsplit("/", 1)[-1]
    row = connection.execute(LATEST_IN_THREAD_QUERY, (rowid, root, thread_guid)).fetchone()
    if row is None:
        return None

    text, body, is_from_me, sender = row
    return Quote(sender=None if is_from_me else sender, text=read_text(text, body))


def get_new_messages(connection, chat_id, after_rowid):
    messages = []
    for rowid, text, body, is_from_me, sender, thread_guid in connection.execute(
        NEW_MESSAGES_QUERY, (chat_id, after_rowid)
    ):
        attachments, attachments_pending = get_attachments(connection, rowid)

        messages.append(
            Message(
                rowid=rowid,
                sender=sender,
                text=read_text(text, body),
                is_from_me=bool(is_from_me),
                attachments=attachments,
                attachments_pending=attachments_pending,
                reply_to=get_quote(connection, thread_guid, rowid),
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
