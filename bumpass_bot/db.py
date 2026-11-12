import plistlib
import sqlite3
from dataclasses import dataclass
from os.path import exists, expanduser

from bumpass_bot import config
from bumpass_bot.events import Attachment, Edit, Message, Quote, Reaction

# Tapbacks/reactions are stored as messages with a non-zero associated_message_type.
# 2000-2005 are the standard tapbacks and 2006 is a custom emoji. Removals (3000+) are left out.
REACTION_EMOJI = {2000: "❤️", 2001: "👍", 2002: "👎", 2003: "😂", 2004: "‼️", 2005: "❓"}
CUSTOM_EMOJI_REACTION = 2006

NEW_MESSAGES_QUERY = """
    SELECT m.ROWID, m.text, m.attributedBody, m.is_from_me, h.id, m.thread_originator_guid,
           m.associated_message_type, m.associated_message_guid, m.associated_message_emoji
    FROM message m
    JOIN chat_message_join cmj ON cmj.message_id = m.ROWID
    JOIN chat c ON c.ROWID = cmj.chat_id
    LEFT JOIN handle h ON h.ROWID = m.handle_id
    WHERE c.chat_identifier = ?
      AND m.ROWID > ?
      AND (m.associated_message_type = 0 OR m.associated_message_type BETWEEN 2000 AND 2006)
    ORDER BY m.ROWID
"""

MESSAGE_BY_GUID_QUERY = """
    SELECT m.text, m.attributedBody, m.is_from_me, h.id
    FROM message m
    LEFT JOIN handle h ON h.ROWID = m.handle_id
    WHERE m.guid = ?
"""

LATEST_IN_THREAD_QUERY = """
    SELECT m.text, m.attributedBody, m.is_from_me, h.id
    FROM message m
    LEFT JOIN handle h ON h.ROWID = m.handle_id
    WHERE m.ROWID < ?
      AND (m.guid = ? OR m.thread_originator_guid = ?)
      AND m.associated_message_type = 0
    ORDER BY m.ROWID DESC
    LIMIT 1
"""

# An edit rewrites the original row in place, so it keeps its ROWID and only date_edited changes.
EDITED_MESSAGES_QUERY = """
    SELECT m.ROWID, m.text, m.attributedBody, m.is_from_me, h.id, m.date_edited,
           m.message_summary_info
    FROM message m
    JOIN chat_message_join cmj ON cmj.message_id = m.ROWID
    JOIN chat c ON c.ROWID = cmj.chat_id
    LEFT JOIN handle h ON h.ROWID = m.handle_id
    WHERE c.chat_identifier = ?
      AND m.date_edited > ?
      AND m.date_retracted = 0
      AND m.ROWID > ?
      AND m.associated_message_type = 0
    ORDER BY m.date_edited
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
class NewEvent:
    event: Message | Reaction
    # True while some attachment hasn't finished downloading to disk.
    attachments_pending: bool = False


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


def get_max_date_edited(connection):
    return connection.execute("SELECT COALESCE(MAX(date_edited), 0) FROM message").fetchone()[0]


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

    return quote_from_row(row)


def quote_from_row(row):
    text, body, is_from_me, sender = row
    return Quote(sender=None if is_from_me else sender, text=read_text(text, body))


def get_reaction_target(connection, associated_guid):
    # The reference looks like "p:<part>/<guid>", or "bp:<guid>" for a balloon.
    guid = associated_guid.rsplit("/", 1)[-1].removeprefix("bp:")
    row = connection.execute(MESSAGE_BY_GUID_QUERY, (guid,)).fetchone()
    return quote_from_row(row) if row else None


def get_new_messages(connection, chat_id, after_rowid):
    """Messages and reactions in the chat with a ROWID past `after_rowid`, oldest first."""
    new_events = []
    for (
        rowid,
        text,
        body,
        is_from_me,
        sender,
        thread_guid,
        message_type,
        associated_guid,
        custom_emoji,
    ) in connection.execute(NEW_MESSAGES_QUERY, (chat_id, after_rowid)):
        if message_type:
            # A reaction row's own text is Messages' summary ("Loved ..."), so it's left out.
            emoji = custom_emoji if message_type == CUSTOM_EMOJI_REACTION else REACTION_EMOJI[message_type]
            reaction = Reaction(
                chat=chat_id,
                rowid=rowid,
                sender=sender,
                is_from_me=bool(is_from_me),
                emoji=emoji,
                target=get_reaction_target(connection, associated_guid),
            )
            new_events.append(NewEvent(reaction))
            continue

        attachments, attachments_pending = get_attachments(connection, rowid)
        message = Message(
            chat=chat_id,
            rowid=rowid,
            sender=sender,
            is_from_me=bool(is_from_me),
            text=read_text(text, body),
            attachments=attachments,
            reply_to=get_quote(connection, thread_guid, rowid),
        )
        new_events.append(NewEvent(message, attachments_pending))

    return new_events


def get_previous_text(summary_info):
    """The text before the latest edit.

    Messages keeps every version in message_summary_info under "ec", oldest first
    with the current one last, keyed by message part.
    """
    if summary_info is None:
        return None

    try:
        history = plistlib.loads(summary_info).get("ec", {})
        for versions in history.values():
            if len(versions) >= 2:
                return read_text(None, versions[-2].get("t"))
    except (ValueError, IndexError):
        pass

    return None


def get_new_edits(connection, chat_id, after_edit, after_rowid):
    """(date_edited, Edit) for edits made after `after_edit` to messages with a ROWID
    past `after_rowid`, oldest edit first."""
    return [
        (
            edited_at,
            Edit(
                chat=chat_id,
                rowid=rowid,
                sender=sender,
                is_from_me=bool(is_from_me),
                text=read_text(text, body),
                previous_text=get_previous_text(summary_info),
            ),
        )
        for rowid, text, body, is_from_me, sender, edited_at, summary_info in connection.execute(
            EDITED_MESSAGES_QUERY, (chat_id, after_edit, after_rowid)
        )
    ]


def get_chat_guid(connection, chat_id):
    row = connection.execute(
        "SELECT guid FROM chat WHERE chat_identifier = ?", (chat_id,)
    ).fetchone()
    if row is None:
        raise ValueError(f"No chat found with identifier {chat_id}")

    return row[0]


def list_group_chats(connection):
    return connection.execute(LIST_GROUP_CHATS_QUERY).fetchall()
