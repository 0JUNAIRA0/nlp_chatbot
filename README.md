# NLP Lab Chatbot

A conversational AI assistant powered by the **Groq API** (`openai/gpt-oss-120b`) with persistent
conversation memory stored in a dedicated **SQLite** database. It ships with two interfaces:
a command-line client and a desktop GUI with a chat-history sidebar.

![Python](https://img.shields.io/badge/Python-3.8%2B-blue)
![LLM](https://img.shields.io/badge/LLM-gpt--oss--120b-orange)
![Database](https://img.shields.io/badge/Database-SQLite-lightgrey)
![Dependencies](https://img.shields.io/badge/Dependencies-none-brightgreen)

---

## Table of Contents

1. [Features](#features)
2. [Architecture](#architecture)
3. [Project Structure](#project-structure)
4. [Getting Started](#getting-started)
5. [Usage](#usage)
6. [Configuration](#configuration)
7. [Database Design](#database-design)
8. [How It Works](#how-it-works)
9. [Troubleshooting](#troubleshooting)
10. [Security Notes](#security-notes)
11. [Limitations and Future Work](#limitations-and-future-work)

---

## Features

- **Large language model chat** through the Groq API (OpenAI-compatible endpoint).
- **Streaming responses**: replies appear token by token instead of after a long wait.
- **Persistent memory**: every conversation is saved in SQLite and can be resumed at any time.
- **Context-aware replies**: the most recent 20 messages are sent with each request.
- **Two interfaces**: terminal (`chatbot.py`) and Tkinter desktop app (`gui.py`).
- **Conversation management**: create, list, load, rename, delete, search and export chats.
- **Custom personality**: change the system prompt per conversation.
- **Bilingual friendly**: the default prompt replies in Bangla when the user writes in Bangla.
- **Zero third-party dependencies**: only the Python standard library is used.

## Architecture

```
 ┌──────────────┐     ┌──────────────┐
 │  chatbot.py  │     │    gui.py    │      Presentation layer
 │  (terminal)  │     │   (Tkinter)  │
 └──────┬───────┘     └──────┬───────┘
        └─────────┬──────────┘
                  ▼
          ┌───────────────┐        HTTPS (streaming)       ┌───────────────┐
          │    bot.py     │ ─────────────────────────────▶ │   Groq API    │
          │  ChatBot class│ ◀───────────────────────────── │ gpt-oss-120b  │
          └───────┬───────┘                                └───────────────┘
                  ▼
          ┌───────────────┐
          │  database.py  │      Data layer
          │ SQLite (.db)  │
          └───────────────┘
```

The presentation layer never talks to the API or database directly. All logic lives in
`ChatBot` (`bot.py`) and the data-access functions (`database.py`), so both interfaces
behave identically.

## Project Structure

```
nlp_chatbot/
├── bot.py            # Core logic: Groq client, streaming, context building
├── database.py       # SQLite schema and data-access functions
├── chatbot.py        # Command-line interface
├── gui.py            # Desktop GUI with conversation sidebar
├── requirements.txt  # Dependency note (none required)
├── .env.example      # Template for configuration
├── .env              # Your private configuration (not shared)
└── chatbot.db        # Created automatically on first run
```

## Getting Started

### Prerequisites

- Python **3.8 or newer** (Tkinter is included with the standard Windows and macOS installers;
  on some Linux distributions install it with `sudo apt install python3-tk`).
- A free Groq API key from <https://console.groq.com/keys>.
- An internet connection.

### Installation

1. Download or clone the project and open a terminal inside the `nlp_chatbot` folder.
2. Create a file named `.env` (or copy `.env.example`) and add your key:

   ```
   GROQ_API_KEY=gsk_your_key_here
   GROQ_MODEL=openai/gpt-oss-120b
   ```

No `pip install` step is needed.

## Usage

### Terminal version

```bash
python chatbot.py
```

| Command | Description |
|---------|-------------|
| `/new` | Start a new conversation |
| `/list` | List all saved conversations |
| `/load <id>` | Continue a previous conversation |
| `/rename <title>` | Rename the current conversation |
| `/delete <id>` | Delete a conversation |
| `/search <word>` | Search across all saved messages |
| `/system <text>` | Set the assistant's personality for this conversation |
| `/export` | Save the current conversation to `conversation_<id>.txt` |
| `/help` | Show the command list |
| `/quit` | Exit |

Any text that does not start with `/` is sent to the model as a message.

### Desktop version

```bash
python gui.py
```

- **+ New chat** starts a fresh conversation.
- Click any conversation in the left sidebar to reopen it.
- **Rename** and **Delete** manage the selected conversation.
- Type in the bottom field and press **Enter** or **Send**.

## Configuration

Settings are read from `.env` or from environment variables.

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `GROQ_API_KEY` | Yes | none | Your Groq API key |
| `GROQ_MODEL` | No | `openai/gpt-oss-120b` | Any model available on your Groq account, e.g. `llama-3.3-70b-versatile` |
| `GROQ_BASE_URL` | No | `https://api.groq.com/openai/v1` | Override the API endpoint |
| `CHATBOT_DB` | No | `chatbot.db` next to the code | Custom path for the database file |

Tunable constants in `bot.py`: `DEFAULT_SYSTEM_PROMPT` (default personality) and
`HISTORY_LIMIT` (number of past messages sent as context, default 20).

## Database Design

SQLite database with two related tables and cascading deletes.

```
conversations                          messages
─────────────                          ────────
id            INTEGER PK               id              INTEGER PK
title         TEXT                     conversation_id INTEGER FK → conversations.id
system_prompt TEXT                     role            TEXT  ('system' | 'user' | 'assistant')
created_at    TEXT                     content         TEXT
updated_at    TEXT                     created_at      TEXT
```

- One conversation has many messages (one-to-many).
- Deleting a conversation removes its messages (`ON DELETE CASCADE`).
- An index on `(conversation_id, id)` keeps history retrieval fast.
- The title is generated automatically from the first user message.

Inspect the data with any SQLite viewer (for example DB Browser for SQLite) or the CLI:

```bash
sqlite3 chatbot.db "SELECT role, content FROM messages ORDER BY id;"
```

## How It Works

1. The user's message is saved to the `messages` table.
2. The system prompt and the last 20 messages of the conversation are loaded from the database.
3. The request is sent to Groq's `/chat/completions` endpoint with `stream: true`.
4. Response chunks are displayed as they arrive (Server-Sent Events).
5. When the stream ends, the full reply is saved as an `assistant` message and the
   conversation's `updated_at` timestamp is refreshed.

In the GUI, the network call runs in a background thread so the window stays responsive.

## Troubleshooting

| Problem | Likely cause and fix |
|---------|----------------------|
| `GROQ_API_KEY not found` | The `.env` file is missing or not in the same folder as `bot.py`. |
| `API error 401` | The key is invalid or revoked. Create a new one in the Groq console. |
| `API error 429` | Rate limit reached. Wait a moment or switch to a smaller model. |
| `Could not reach the API` | No internet, or a firewall or proxy is blocking `api.groq.com`. |
| `API error 400 ... model` | The model name in `GROQ_MODEL` is wrong or no longer available. |
| GUI does not open | Tkinter is missing. Install `python3-tk` (Linux) or reinstall Python with Tkinter, or use `chatbot.py`. |
| `python` not found | Try `python3` (macOS/Linux) or `py` (Windows). |

## Security Notes

- Keep `.env` private. Never commit it to Git or include it when sharing the project.
  Add it to `.gitignore`:

  ```
  .env
  chatbot.db
  ```
- If a key is ever exposed, revoke it in the Groq console and create a new one.
- Conversations are stored unencrypted in `chatbot.db`; do not enter sensitive personal data.

## Limitations and Future Work

- Context is limited to the last 20 messages; long conversations lose older detail.
  A summarization step could compress older history.
- Responses depend on the hosted model and may contain mistakes.
- Possible extensions: sentiment or intent analysis, retrieval-augmented generation (RAG)
  over local documents, multi-user accounts, and a web interface.

## License

Developed for  NLP lab .
