"""Copies everything said in one chat into the other.

AppleScript can only send plain text and files, so replies, reactions and edits
go out as text that quotes the message they point at.
"""

from bumpass_bot import config
from bumpass_bot.events import Edit, Message, Reaction
from bumpass_bot.formatting import italic, truncate

QUOTE_MARK = "↪"
REACTION_PREFIX = "reacted "
QUOTE_MAX_CHARS = 60
# A forward leaves out the name line when the bot's last message in that chat was a
# forward from the same person, nothing else was said since, and it was this recent.
GROUP_SECONDS = 10 * 60


def handle(bot, event):
    destination = destination_for(event.chat)
    if destination is None:
        return

    match event:
        case Message():
            forward_message(bot, event, destination)
        case Reaction() if config.REACTIONS:
            forward_reaction(bot, event, destination)
        case Edit() if config.EDITS:
            forward_edit(bot, event, destination)


def destination_for(chat_id):
    chat_a, chat_b = config.get_chat_ids()
    if chat_id == chat_a:
        return chat_b

    if chat_id == chat_b:
        return chat_a

    return None


def forward_message(bot, message, destination):
    lines = header(bot, message, destination)
    if message.reply_to:
        lines.append(format_quote(bot, message.reply_to))

    if message.text:
        lines.append(message.text)

    key = group_key(message)
    # An own or grouped message with only files has no text to send.
    if lines:
        bot.send(destination, "\n".join(lines), key=key)

    for attachment in message.attachments:
        bot.send_file(destination, attachment.path, attachment.mime_type, key=key)


def forward_reaction(bot, reaction, destination):
    # Without the message that was reacted to, "reacted 😂" says nothing.
    if not reaction.target or is_forwarded_reaction(reaction.target):
        return

    lines = header(bot, reaction, destination)
    lines.append(format_quote(bot, reaction.target))
    lines.append(f"{REACTION_PREFIX}{reaction.emoji}")
    bot.send(destination, "\n".join(lines), key=group_key(reaction))


def forward_edit(bot, edit, destination):
    if not edit.text:
        return

    # Always named, since "edited" is the point of the message.
    lines = [] if edit.is_from_me else [f"{bot.name(edit.sender)} edited:"]
    if edit.previous_text:
        lines.append(quote_line(f"was: {shorten(edit.previous_text)}"))

    lines.append(edit.text)
    bot.send(destination, "\n".join(lines), key=group_key(edit))


def group_key(event):
    # Own messages have no name line to leave out, so they never group.
    return None if event.is_from_me else event.sender


def header(bot, event, destination):
    """The name line, or nothing for own messages and ones grouped under the previous forward."""
    if event.is_from_me:
        return []

    # A missing sender handle never groups, so "Unknown:" is always shown.
    if event.sender is not None and bot.last_send_key(destination, GROUP_SECONDS) == event.sender:
        return []

    return [f"{bot.name(event.sender)}:"]


def shorten(text):
    # Drop a quote line of its own, which is there when the text is something the bot forwarded.
    own_lines = (line for line in text.splitlines() if not line.startswith(QUOTE_MARK))
    return truncate(" ".join(own_lines), QUOTE_MAX_CHARS) or "[attachment]"


def quote_line(content):
    return italic(f'{QUOTE_MARK} "{content}"')


def format_quote(bot, quote):
    snippet = shorten(quote.text)

    # A quote of our own account's message has no author, and when that message
    # was itself forwarded by the bot its text already starts with the original sender.
    if quote.sender is None:
        return quote_line(snippet)

    return quote_line(f"{bot.name(quote.sender)}: {snippet}")


def is_forwarded_reaction(quote):
    """Whether the quoted message is a reaction the bot forwarded as text."""
    lines = quote.text.splitlines()
    return (
        len(lines) > 1
        and lines[-1].startswith(REACTION_PREFIX)
        and any(line.startswith(QUOTE_MARK) for line in lines)
    )
