from os import environ
from os.path import dirname, expanduser, join

from dotenv import load_dotenv

load_dotenv(join(dirname(dirname(__file__)), ".env"))

DB_PATH = expanduser("~/Library/Messages/chat.db")
POLL_SECONDS = 2
SELF_NAME = environ.get("SELF_NAME", "Me")
# When set, forwarded messages are printed instead of sent.
DRY_RUN = environ.get("DRY_RUN") == "1"


def get_chat_ids():
    return environ["CHAT_A_ID"], environ["CHAT_B_ID"]
