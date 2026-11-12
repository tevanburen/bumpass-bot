"""Replies to "/test" so people can check the bot is running. The command isn't forwarded."""

from bumpass_bot.handlers.command import is_command

REPLY = "The Bumpass Bot is active"


def handle(bot, event):
    if not is_command(event, "/test"):
        return False

    bot.send(event.chat, REPLY)
    return True
