"""Replies to "/members" with who is in each watched chat. The command isn't forwarded."""

from bumpass_bot.handlers.command import is_command


def handle(bot, event):
    if not is_command(event, "/members"):
        return False

    sections = []
    for chat_id in bot.chat_ids:
        names = sorted((bot.name(handle) for handle in bot.members(chat_id)), key=str.casefold)
        sections.append(f"{bot.chat_name(chat_id)} ({len(names)}):\n{', '.join(names)}")

    bot.send(event.chat, "\n\n".join(sections))
    return True
