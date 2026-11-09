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

Reactions are forwarded the same way, as a message that quotes the one reacted to. Messages can't send a real tapback through AppleScript, and removed reactions aren't forwarded. Reacting to one of these forwarded reactions does nothing:

```
Alex:
↪ "Sam: dinner at 7?"
reacted 😂
```

The quote line is italic. AppleScript can't send formatted text, so it uses Unicode italic letters (𝘭𝘪𝘬𝘦 𝘵𝘩𝘪𝘴); digits, punctuation and accented letters stay upright.

Messages you send yourself are forwarded without a header. Images and other files are forwarded after the header as separate messages.

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
| `ONE_WAY` | Set to `1` to only forward A -> B (default is both directions) |
| `NAME_OVERRIDES` | `handle=Name` pairs, comma-separated, checked before Contacts |
| `REACTIONS` | Set to `0` to stop forwarding reactions (default is on) |

### Permissions

- **Full Disk Access** for whatever launches the bot (terminal, launchd job), to read `chat.db` and Contacts.
- **Automation** access to Messages, prompted on the first send.

## Run

```bash
uv run python -m bumpass_bot.main
```

Only messages that arrive after startup are forwarded.

## How it works

- `db.py` reads `chat.db` read-only, tracking a last-seen `ROWID` per chat.
- `main.py` forwards new messages in each direction. Incoming attachments are held up to 60s while they download.
- `sent_tracker.py` remembers what the bot sent so its own messages are ignored when they show up in the destination chat. This is what stops infinite loops in two-way mode.
- `names.py` maps phone numbers and emails to names from Contacts.
- `send.py` sends text and files with `osascript`.

## Not handled yet

Edits and unsends, removed reactions, stickers, and link previews. The last-seen `ROWID` isn't persisted, so messages that arrive while the bot is down are skipped.
