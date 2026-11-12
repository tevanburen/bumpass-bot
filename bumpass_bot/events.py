"""What handlers receive. `chat` is the chat_identifier the event happened in, and
`sender` is the sender's phone number or email (use bot.name() for a display name)."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Attachment:
    path: str
    mime_type: str


@dataclass(frozen=True)
class Quote:
    """Another message an event points at, such as the one a reply is to."""

    # None when the quoted message was sent from this Mac's account.
    sender: str | None
    text: str


@dataclass(frozen=True)
class Message:
    chat: str
    rowid: int
    sender: str | None
    # Sent from this Mac's account. The bot's own sends never reach handlers.
    is_from_me: bool
    text: str
    attachments: tuple[Attachment, ...] = ()
    # The message this one replies to, when it is a reply and the original is still around.
    reply_to: Quote | None = None


@dataclass(frozen=True)
class Reaction:
    chat: str
    rowid: int
    sender: str | None
    is_from_me: bool
    emoji: str
    # The message reacted to, if it is still around.
    target: Quote | None


@dataclass(frozen=True)
class Edit:
    """An edit to a message that handlers already got as a Message."""

    chat: str
    rowid: int
    sender: str | None
    is_from_me: bool
    # The message as it reads now.
    text: str
    # What it said before this edit, if Messages kept the history.
    previous_text: str | None


type Event = Message | Reaction | Edit
