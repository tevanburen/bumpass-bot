"""Slash commands.

A message that is exactly a command, ignoring case and surrounding spaces, runs it
in the chat it was sent in and isn't forwarded. To add one, write a function that
takes the bot and the message, and add it to COMMANDS.
"""

from bumpass_bot.events import Message


def test(bot, message):
    bot.send(message.chat, "The Bumpass Bot is active")


def members(bot, message):
    # chat.db doesn't list this Mac's own account as a member, so the bot isn't counted.
    sections = []
    for chat_id in bot.chat_ids:
        names = sorted((bot.name(handle) for handle in bot.members(chat_id)), key=str.casefold)
        sections.append(f"{bot.chat_name(chat_id)} ({len(names)}):\n{', '.join(names)}")

    bot.send(message.chat, "\n\n".join(sections))


COMMANDS = {
    "/test": test,
    "/members": members,
}


def handle(bot, event):
    if not isinstance(event, Message) or event.attachments:
        return False

    command = COMMANDS.get(event.text.strip().casefold())
    if command is None:
        return False

    command(bot, event)
    return True
