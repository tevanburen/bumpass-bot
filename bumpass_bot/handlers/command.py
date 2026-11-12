from bumpass_bot.events import Message


def is_command(event, command):
    """Whether the event is a text-only message that is exactly `command`, ignoring case and spaces."""
    return (
        isinstance(event, Message)
        and not event.attachments
        and event.text.strip().casefold() == command
    )
