import subprocess

# Text and target are passed as argv so no escaping is needed.
SEND_SCRIPT = """
on run argv
    tell application "Messages" to send (item 1 of argv) to chat id (item 2 of argv)
end run
"""


def send_message(chat_guid, text):
    subprocess.run(
        ["osascript", "-e", SEND_SCRIPT, text, chat_guid],
        check=True,
        capture_output=True,
        text=True,
    )


SEND_FILE_SCRIPT = """
on run argv
    tell application "Messages" to send (POSIX file (item 1 of argv)) to chat id (item 2 of argv)
end run
"""


def send_file(chat_guid, path):
    subprocess.run(
        ["osascript", "-e", SEND_FILE_SCRIPT, path, chat_guid],
        check=True,
        capture_output=True,
        text=True,
    )
