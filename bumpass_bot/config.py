from os import environ
from os.path import dirname, expanduser, join

from dotenv import load_dotenv

load_dotenv(join(dirname(dirname(__file__)), ".env"))

DB_PATH = expanduser("~/Library/Messages/chat.db")
POLL_SECONDS = 2
# How long to wait for an incoming attachment to finish downloading before forwarding without it.
ATTACHMENT_WAIT_SECONDS = 60
# A stuck osascript (e.g. an unanswered Automation prompt) would otherwise freeze the polling loop.
SEND_TIMEOUT_SECONDS = 30


# When set, reactions are forwarded as text.
REACTIONS = environ.get("REACTIONS") == "1"
# When set, edits are forwarded as a new message.
EDITS = environ.get("EDITS") == "1"
# When set, sends are logged instead of sent, for running against your own chats without posting.
DRY_RUN = environ.get("DRY_RUN") == "1"


def get_chat_ids():
    return environ["CHAT_A_ID"], environ["CHAT_B_ID"]
