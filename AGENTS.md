# AGENTS.md

Python 3.13 project managed with uv. See README.md for setup and behavior.

## Commands

- `uv sync` installs dependencies.
- `uv run python -m bumpass_bot.main` runs the bot. `uv run python -m bumpass_bot.list_chats` lists group chats.
- No tests, and don't add any unless asked.

## Layout

- `bumpass_bot/main.py`: polling loop and forwarding logic.
- `bumpass_bot/db.py`: read-only `chat.db` queries (messages, attachments, chat GUIDs).
- `bumpass_bot/send.py`: AppleScript sending via `osascript`.
- `bumpass_bot/sent_tracker.py`: loop guard for two-way forwarding.
- `bumpass_bot/names.py`: Contacts lookup with `NAME_OVERRIDES`.
- `bumpass_bot/config.py`: env config.

## Gotchas

- Never write to `chat.db`; it's opened with `mode=ro`.
- Sending to a chat uses `chat.guid` (`any;+;...`), not `chat_identifier`.
- `message.text` is often NULL on recent macOS; the text is in `attributedBody` (`db.decode_attributed_body`).
- The bot's own sends come back as `is_from_me` rows in the destination chat. `SentTracker` matches them by text (and by top-level MIME type for files). Any change to what gets sent, such as header format, must keep the recorded key identical to the text sent, or two-way mode will loop.
- The loop guard is loose for files on purpose: swallowing one of the user's own photos is preferred to a loop.
- Sends and tests post to real chats. `CHAT_A_ID` and `CHAT_B_ID` in `.env` are throwaway test chats; don't send messages yourself, the user runs live tests.
- `.env` holds chat IDs and is git-ignored.

## Style

Plain functions and small dataclasses, no classes beyond `Chat`, `Message`, `Attachment`, `SentTracker` and `NameResolver`. Comments only where the reason isn't obvious.
