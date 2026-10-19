# NLP Lab Chatbot (Groq API + SQLite database)

A chatbot that uses the **Groq API** (Llama 3.3 70B) and keeps every conversation in a separate
SQLite database (`chatbot.db`), so chats are saved and can be continued later.

## Files

| File | Purpose |
|------|---------|
| `database.py` | Separate database layer (SQLite): conversations + messages tables |
| `bot.py` | Core logic: Groq streaming call, memory (last 20 messages sent as context) |
| `chatbot.py` | Terminal version |
| `gui.py` | Window version with a chat-history sidebar |
| `.env` | Your Groq key (`GROQ_API_KEY=gsk_...`) |

## Setup

1. Install Python 3.8+. Nothing else to install (standard library only).
2. Put your key in `.env`:  `GROQ_API_KEY=gsk_...`  (key from https://console.groq.com/keys)

## Run

```
python chatbot.py     # terminal
python gui.py         # window
```

## Terminal commands

`/new`, `/list`, `/load <id>`, `/rename <title>`, `/delete <id>`, `/search <word>`,
`/system <text>`, `/export`, `/help`, `/quit`

## Database design

```
conversations(id PK, title, system_prompt, created_at, updated_at)
messages(id PK, conversation_id FK -> conversations.id, role, content, created_at)
```

Deleting a conversation also deletes its messages (ON DELETE CASCADE).

## How it works

1. The user message is saved to the database.
2. The last 20 messages + system prompt are sent to Groq's chat completions endpoint (streaming).
3. The reply is printed token by token and saved as an `assistant` message.
