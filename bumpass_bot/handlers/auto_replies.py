"""Automatic replies to messages that contain a phrase.

A message containing a phrase in AUTO_REPLIES, anywhere and ignoring case, runs its
reply. To add one, write a function that takes the bot and the message, and add it
to AUTO_REPLIES. A message containing several phrases gets each reply, in table order.

This runs after forwarding, so the message is still forwarded and the other chat
sees it before any reply.
"""

import random

from bumpass_bot.events import Message


def send_to_both_chats(bot, text):
    for chat_id in bot.chat_ids:
        bot.send(chat_id, text)


def _send_percent(bot, label):
    send_to_both_chats(bot, f"{random.randint(0, 100)}% {label}")


def based_check(bot, message):
    _send_percent(bot, "Based")


AUTO_REPLIES = {
    "based check": based_check,
}


def handle(bot, event):
    if not isinstance(event, Message):
        return False

    text = event.text.casefold()
    for phrase, reply in AUTO_REPLIES.items():
        if phrase in text:
            reply(bot, event)

    return False
