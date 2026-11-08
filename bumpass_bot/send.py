import subprocess

from bumpass_bot import config

# Text and target are passed as argv so no escaping is needed.
SEND_SCRIPT = """
on run argv
    tell application "Messages" to send (item 1 of argv) to chat id (item 2 of argv)
end run
"""

SEND_FILE_SCRIPT = """
on run argv
    tell application "Messages" to send (POSIX file (item 1 of argv)) to chat id (item 2 of argv)
end run
"""


def run_osascript(script, *args):
    result = subprocess.run(
        ["osascript", "-e", script, *args],
        capture_output=True,
        text=True,
        timeout=config.SEND_TIMEOUT_SECONDS,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or f"osascript exited {result.returncode}")


def send_message(chat_guid, text):
    run_osascript(SEND_SCRIPT, text, chat_guid)


def send_file(chat_guid, path):
    run_osascript(SEND_FILE_SCRIPT, path, chat_guid)
