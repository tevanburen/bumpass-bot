from os import environ
from os.path import dirname, expanduser, join

from dotenv import load_dotenv

load_dotenv(join(dirname(dirname(__file__)), ".env"))

DB_PATH = expanduser("~/Library/Messages/chat.db")
POLL_SECONDS = 2


def get_chat_ids():
    return environ["CHAT_A_ID"], environ["CHAT_B_ID"]
