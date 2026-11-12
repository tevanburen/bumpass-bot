import logging

from bumpass_bot import config
from bumpass_bot.bot import Bot
from bumpass_bot.handlers import HANDLERS


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    Bot(config.get_chat_ids(), HANDLERS).run()


if __name__ == "__main__":
    main()
