# AGENTS.md

Python 3.13 project managed with uv. See README.md for setup and behavior.

## Commands

- `uv sync` installs dependencies.
- `uv run bumpass-bot` runs the bot. `uv run python -m bumpass_bot.list_chats` lists group chats.
- No tests, and don't add any unless asked.

## Layout

See "How it works", "Layout", "Adding a command" and "Adding a handler" in README.md, and keep them current when files move.

## Gotchas

- Never write to `chat.db`; it's opened with `mode=ro`.
- Sending to a chat uses `chat.guid` (`any;+;...`), not `chat_identifier`.
- `message.text` is often NULL on recent macOS; the text is in `attributedBody` (`db.decode_attributed_body`).
- The bot's own sends come back as `is_from_me` rows in that chat. `Bot.send` records the exact text in `SentTracker` (top-level MIME type for files), and `Bot` drops matching rows before handlers see them. Handlers must send through `bot.send`/`bot.send_file`, never `send.py`, or two-way forwarding will loop.
- The loop guard is loose for files on purpose: swallowing one of the user's own photos is preferred to a loop.
- `CHAT_A_ID` and `CHAT_B_ID` in `.env` on the Mac Studio are the real group chats. Never run the bot or send anything yourself there; use `DRY_RUN=1` to check behavior, and the user runs live tests.
- `.env` holds chat IDs and is git-ignored.

## Style

Plain functions and small frozen dataclasses. The only stateful classes are `Bot`, `SentTracker` and `NameResolver`; handlers are plain functions. Log with `logging`, not `print`. Comments only where the reason isn't obvious.
