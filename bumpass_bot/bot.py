import logging
import mimetypes
import time
from dataclasses import dataclass, replace

from bumpass_bot import config, db
from bumpass_bot import send as osascript
from bumpass_bot.events import Message
from bumpass_bot.names import NameResolver
from bumpass_bot.sent_tracker import SentTracker

logger = logging.getLogger(__name__)


@dataclass
class ChatState:
    id: str
    last_rowid: int
    # The newest date_edited we've handled.
    last_edit: int
    # When we started waiting on the current message's attachments to download.
    waiting_since: float | None = None


class Bot:
    """Polls chat.db for new events in the watched chats and runs each one through the handlers.

    A handler is called as handler(bot, event) with a Message, Reaction or Edit,
    in list order, and returns True to stop the handlers after it.
    Only what happens after startup is handled.
    """

    def __init__(self, chat_ids, handlers):
        self.chat_ids = tuple(chat_ids)
        self.handlers = handlers
        self._connection = db.connect()
        self._names = NameResolver()
        self._sent = SentTracker()
        # Fails at startup on a wrong chat ID instead of on the first send.
        self._guids = {chat_id: db.get_chat_guid(self._connection, chat_id) for chat_id in chat_ids}

        self._start_rowid = db.get_max_rowid(self._connection)
        last_edit = db.get_max_date_edited(self._connection)
        self._chats = [ChatState(chat_id, self._start_rowid, last_edit) for chat_id in chat_ids]

        logger.info(
            "Watching %s, history ignored up to ROWID %d", ", ".join(chat_ids), self._start_rowid
        )
        if config.DRY_RUN:
            logger.info("Dry run: sends are logged, not sent")

    def name(self, handle):
        """Contact name for a phone number or email, or the handle itself if there is none."""
        return self._names.lookup(handle)

    def chat_name(self, chat_id):
        """The chat's display name, or its chat_identifier if it has none."""
        return db.get_chat_name(self._connection, chat_id) or chat_id

    def members(self, chat_id):
        """Handles of everyone in the chat, not counting the bot's own account."""
        return db.get_chat_members(self._connection, chat_id)

    def send(self, chat_id, text):
        """Send text to a chat by chat_identifier. Logs and returns False if it fails."""
        logger.info("Send to %s: %r", chat_id, text)
        if config.DRY_RUN:
            return True

        try:
            osascript.send_message(self._guid(chat_id), text)
        except Exception:
            logger.exception("Error sending to %s", chat_id)
            return False

        # The send comes back as an is_from_me message in that chat; this is how it gets skipped.
        self._sent.record(chat_id, text)
        return True

    def send_file(self, chat_id, path, mime_type=None):
        """Send a file to a chat. mime_type is guessed from the file name if not given."""
        mime_type = mime_type or mimetypes.guess_type(path)[0] or "application/octet-stream"
        logger.info("Send file to %s: %s", chat_id, path)
        if config.DRY_RUN:
            return True

        try:
            osascript.send_file(self._guid(chat_id), path)
        except Exception:
            logger.exception("Error sending file to %s", chat_id)
            return False

        self._sent.record_file(chat_id, mime_type)
        return True

    def run(self):
        while True:
            time.sleep(config.POLL_SECONDS)

            for chat in self._chats:
                # Edits go first, so an edit to a message the handlers haven't seen yet
                # is skipped and the message arrives with its edited text instead.
                try:
                    self._handle_new_edits(chat)
                except Exception:
                    logger.exception("Error reading edits from %s, will retry next poll", chat.id)

                try:
                    self._handle_new_messages(chat)
                except Exception:
                    logger.exception("Error reading messages from %s, will retry next poll", chat.id)

    def _guid(self, chat_id):
        # Sending goes by chat.guid ("any;+;..."), not chat_identifier.
        if chat_id not in self._guids:
            self._guids[chat_id] = db.get_chat_guid(self._connection, chat_id)

        return self._guids[chat_id]

    def _handle_new_edits(self, chat):
        edits = db.get_new_edits(self._connection, chat.id, chat.last_edit, self._start_rowid)

        for edited_at, edit in edits:
            chat.last_edit = edited_at
            if edit.rowid <= chat.last_rowid:
                self._dispatch(edit)

    def _handle_new_messages(self, chat):
        for new in db.get_new_messages(self._connection, chat.id, chat.last_rowid):
            if new.attachments_pending:
                if chat.waiting_since is None:
                    chat.waiting_since = time.monotonic()

                if time.monotonic() - chat.waiting_since < config.ATTACHMENT_WAIT_SECONDS:
                    # Leave the watermark alone and retry this message next poll.
                    return

                logger.warning(
                    "[%s %d] Attachment never finished downloading, skipping it",
                    chat.id,
                    new.event.rowid,
                )

            chat.waiting_since = None

            # Advance first so a failure is logged and skipped, not retried into duplicates.
            chat.last_rowid = new.event.rowid

            event = self._without_own_sends(new.event)
            if event is not None:
                self._dispatch(event)

    def _without_own_sends(self, event):
        """Strip what the bot itself sent, which comes back as is_from_me in that chat.

        Returns None for a message with nothing left."""
        if not isinstance(event, Message):
            return event

        text = event.text
        attachments = event.attachments
        if event.is_from_me:
            if text and self._sent.consume(event.chat, text):
                text = ""
            attachments = tuple(
                attachment
                for attachment in attachments
                if not self._sent.consume_file(event.chat, attachment.mime_type)
            )

        if not text and not attachments:
            return None

        return replace(event, text=text, attachments=attachments)

    def _dispatch(self, event):
        for handler in self.handlers:
            try:
                if handler(self, event):
                    return
            except Exception:
                logger.exception("Handler %s failed on %s", handler.__module__, event)
