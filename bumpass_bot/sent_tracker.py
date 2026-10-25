import time

EXPIRY_SECONDS = 300


class SentTracker:
    """Remembers what the bot sent so it can ignore those messages when they
    show up in the destination chat, which would otherwise forward them back
    and loop forever."""

    def __init__(self):
        self._pending = {}

    def record(self, chat_id, text):
        self._pending.setdefault(chat_id, []).append((text, time.monotonic()))

    def consume(self, chat_id, text):
        """Return True (and forget the entry) if the bot sent this text to the chat."""
        cutoff = time.monotonic() - EXPIRY_SECONDS
        entries = [
            (sent_text, sent_at)
            for sent_text, sent_at in self._pending.get(chat_id, [])
            if sent_at >= cutoff
        ]

        for index, (sent_text, _) in enumerate(entries):
            if sent_text == text:
                del entries[index]
                self._pending[chat_id] = entries
                return True

        self._pending[chat_id] = entries
        return False
