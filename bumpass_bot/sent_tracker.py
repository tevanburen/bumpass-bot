import time

TEXT_EXPIRY_SECONDS = 300
# Files can't be matched exactly, so keep the window short to limit swallowing
# files the user sends themselves.
FILE_EXPIRY_SECONDS = 60


def file_key(attachment):
    # Top-level MIME type only, in case Messages transcodes within a type (e.g. mov -> mp4).
    return ("file", attachment.mime_type.split("/")[0])


class SentTracker:
    """Remembers what the bot sent so it can ignore those messages when they
    show up in the destination chat, which would otherwise forward them back
    and loop forever.

    Keys are the sent text for text messages, or file_key(...) for files."""

    def __init__(self):
        self._pending = {}

    def record(self, chat_id, key, ttl=TEXT_EXPIRY_SECONDS):
        self._pending.setdefault(chat_id, []).append((key, time.monotonic() + ttl))

    def consume(self, chat_id, key):
        """Return True (and forget the entry) if the bot sent this to the chat."""
        now = time.monotonic()
        entries = [
            (sent_key, expires_at)
            for sent_key, expires_at in self._pending.get(chat_id, [])
            if expires_at >= now
        ]

        for index, (sent_key, _) in enumerate(entries):
            if sent_key == key:
                del entries[index]
                self._pending[chat_id] = entries
                return True

        self._pending[chat_id] = entries
        return False

    def record_file(self, chat_id, attachment):
        self.record(chat_id, file_key(attachment), FILE_EXPIRY_SECONDS)

    def consume_file(self, chat_id, attachment):
        return self.consume(chat_id, file_key(attachment))
