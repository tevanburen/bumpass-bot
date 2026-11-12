# bumpass-bot

Links two iMessage group chats (which cap at 32 participants) by forwarding messages between them. It runs on a Mac, polls `~/Library/Messages/chat.db` for new messages, and sends copies to the other chat through AppleScript.

A message from Alex in ChatA shows up in ChatB as:

```
Alex:
message text
```

Replies include a one-line quote of the original (shortened to 60 characters), since iMessage can't send an inline reply through AppleScript:

```
Alex:
↪ "Sam: dinner at 7?"
yes
```

With `REACTIONS=1`, reactions are forwarded the same way, as a message that quotes the one reacted to. Messages can't send a real tapback through AppleScript, and removed reactions aren't forwarded. Reacting to one of these forwarded reactions does nothing:

```
Alex:
↪ "Sam: dinner at 7?"
reacted 😂
```

With `EDITS=1`, edits are sent as a new message with the previous text, since a sent message can't be changed through AppleScript:

```
Alex edited:
↪ "was: dinner at 6?"
dinner at 7?
```

The quote lines are italic. AppleScript can't send formatted text, so it uses Unicode italic letters (𝘭𝘪𝘬𝘦 𝘵𝘩𝘪𝘴); digits, punctuation and accented letters stay upright.

Messages you send yourself are forwarded without a header. Images and other files are forwarded after the header as separate messages.

### Commands

Send one of these on its own in either chat. The bot answers in that chat, and the command isn't forwarded.

| Command | Reply |
| --- | --- |
| `/test` | "The Bumpass Bot is active" |
| `/members` | Everyone in each chat, not counting the bot's account |

## Setup

Requires macOS and [uv](https://docs.astral.sh/uv/).

```bash
uv sync
cp .env.example .env
uv run python -m bumpass_bot.list_chats
```

`list_chats` prints the `chat_identifier` of every group chat. Put the two you want in `.env`.

| Variable | Purpose |
| --- | --- |
| `CHAT_A_ID`, `CHAT_B_ID` | `chat_identifier` of each chat |
| `REACTIONS` | Set to `1` to forward reactions (default is off) |
| `EDITS` | Set to `1` to forward edits (default is off) |
| `DRY_RUN` | Set to `1` to log sends instead of sending them |

### Permissions

- **Full Disk Access** for whatever launches the bot (terminal, launchd job), to read `chat.db` and Contacts.
- **Automation** access to Messages, prompted on the first send.

## Run

```bash
uv run bumpass-bot
```

Only messages that arrive after startup are handled. To try changes on your own Mac without posting anything, point `.env` at your own chats and run with `DRY_RUN=1`.

## How it works

`Bot` (`bot.py`) polls `chat.db` every 2 seconds for new events in the watched chats and runs each one through the handlers in `handlers/__init__.py`, in order. Forwarding is one handler (`handlers/forward.py`).

Events (`events.py`) are `Message`, `Reaction` and `Edit`. Each has the `chat` it happened in, the `sender` handle and `is_from_me`.

- `Message` has `text`, `attachments` and `reply_to`, a `Quote` of the message it replies to.
- `Reaction` has `emoji` and `target`, the message reacted to.
- `Edit` has the new `text` and `previous_text`. It only comes for messages handlers already got.

Before an event reaches handlers, the bot:

- waits up to 60s for incoming attachments to download.
- drops its own sends, which come back as `is_from_me` messages. This is what stops two-way forwarding from looping.

### Layout

All in `bumpass_bot/`:

| File | What it does |
| --- | --- |
| `main.py` | Entry point (`uv run bumpass-bot`). Sets up logging and runs the bot. |
| `bot.py` | `Bot`: the polling loop, attachment waiting, the loop guard, and the `send`/`send_file`/`name`/`members` API handlers use. |
| `events.py` | `Message`, `Reaction`, `Edit`, `Quote`, `Attachment`: what handlers receive. |
| `handlers/__init__.py` | `HANDLERS`, the order events run through. |
| `handlers/commands.py` | Slash commands. |
| `handlers/forward.py` | Forwarding between the two chats, and its text format. |
| `db.py` | Read-only `chat.db` queries. |
| `send.py` | Sending with `osascript`. Only `Bot` calls it. |
| `sent_tracker.py` | Remembers the bot's sends so their echoes are dropped. |
| `names.py` | Phone number and email to Contacts name. |
| `formatting.py` | Text helpers such as `italic`. |
| `config.py` | Settings from `.env`. |
| `list_chats.py` | Prints group chat IDs for setup. |

## Adding a command

Write a function that takes the bot and the message, and add it to `COMMANDS` in `handlers/commands.py`:

```python
def test(bot, message):
    bot.send(message.chat, "The Bumpass Bot is active")


COMMANDS = {
    "/test": test,
    "/members": members,
}
```

A message that is exactly the command runs it, ignoring case and surrounding spaces. A command isn't forwarded, and its reply stays in the chat it was sent in.

## Adding a handler

For anything other than a command, write a handler. It's a function that takes the bot and an event (any `Message`, `Reaction` or `Edit`). Add it to `HANDLERS` in `handlers/__init__.py`. `commands.handle` and `forward.handle` are both handlers.

- Return `True` to stop the handlers after it. Put it before `forward.handle` if it should keep something from being forwarded.
- Send with `bot.send(chat, text)` and `bot.send_file(chat, path)`, never `send.py` directly. The bot needs to know what it sent, or its own messages come back as new events.
- `bot.name(handle)` gives a display name. `bot.chat_ids` are the watched chats, and `bot.chat_name(chat)` and `bot.members(chat)` describe them.
- A handler that raises is logged and skipped. The other handlers still run.

## Not handled yet

Unsends, removed reactions, stickers, and link previews. The last-seen `ROWID` isn't persisted, so messages that arrive while the bot is down are skipped.
