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
    lines = header(bot, message, ":")
    if message.reply_to:
        lines.append(format_quote(bot, message.reply_to))

    if message.text:
        lines.append(message.text)

    # An own message with only files has no text to send.
    if lines:
        bot.send(destination, "\n".join(lines))

    for attachment in message.attachments:
        bot.send_file(destination, attachment.path, attachment.mime_type)


def forward_reaction(bot, reaction, destination):
    # Without the message that was reacted to, "reacted 😂" says nothing.
    if not reaction.target or is_forwarded_reaction(reaction.target):
        return

    lines = header(bot, reaction, ":")
    lines.append(format_quote(bot, reaction.target))
    lines.append(f"{REACTION_PREFIX}{reaction.emoji}")
    bot.send(destination, "\n".join(lines))


def forward_edit(bot, edit, destination):
    if not edit.text:
        return

    lines = header(bot, edit, " edited:")
    if edit.previous_text:
        lines.append(quote_line(f"was: {shorten(edit.previous_text)}"))

    lines.append(edit.text)
    bot.send(destination, "\n".join(lines))


def header(bot, event, suffix):
    # Own messages are forwarded without a header.
    if event.is_from_me:
        return []

    return [f"{bot.name(event.sender)}{suffix}"]


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
