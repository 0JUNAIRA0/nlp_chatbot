"""
database.py - Separate SQLite database layer for the chatbot.

Tables
------
conversations(id, title, system_prompt, created_at, updated_at)
messages(id, conversation_id, role, content, created_at)

Only the standard library is used (sqlite3), so no extra install is needed.
"""

import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime

DB_PATH = os.environ.get("CHATBOT_DB", os.path.join(os.path.dirname(os.path.abspath(__file__)), "chatbot.db"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS conversations (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    title         TEXT NOT NULL DEFAULT 'New chat',
    system_prompt TEXT,
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS messages (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id INTEGER NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    role            TEXT NOT NULL CHECK (role IN ('system', 'user', 'assistant')),
    content         TEXT NOT NULL,
    created_at      TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_messages_conv ON messages(conversation_id, id);
"""


def _now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


@contextmanager
def connect(db_path=None):
    conn = sqlite3.connect(db_path or DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db(db_path=None):
    with connect(db_path) as conn:
        conn.executescript(SCHEMA)


# ----------------------------------------------------------------------------
# Conversations
# ----------------------------------------------------------------------------
def create_conversation(title="New chat", system_prompt=None, db_path=None):
    now = _now()
    with connect(db_path) as conn:
        cur = conn.execute(
            "INSERT INTO conversations (title, system_prompt, created_at, updated_at) VALUES (?, ?, ?, ?)",
            (title, system_prompt, now, now),
        )
        return cur.lastrowid


def list_conversations(db_path=None):
    with connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT c.id, c.title, c.updated_at,
                   (SELECT COUNT(*) FROM messages m WHERE m.conversation_id = c.id) AS message_count
            FROM conversations c
            ORDER BY c.updated_at DESC, c.id DESC
            """
        ).fetchall()
        return [dict(r) for r in rows]


def get_conversation(conversation_id, db_path=None):
    with connect(db_path) as conn:
        row = conn.execute("SELECT * FROM conversations WHERE id = ?", (conversation_id,)).fetchone()
        return dict(row) if row else None


def rename_conversation(conversation_id, title, db_path=None):
    with connect(db_path) as conn:
        conn.execute("UPDATE conversations SET title = ?, updated_at = ? WHERE id = ?",
                     (title, _now(), conversation_id))


def set_system_prompt(conversation_id, system_prompt, db_path=None):
    with connect(db_path) as conn:
        conn.execute("UPDATE conversations SET system_prompt = ?, updated_at = ? WHERE id = ?",
                     (system_prompt, _now(), conversation_id))


def delete_conversation(conversation_id, db_path=None):
    with connect(db_path) as conn:
        conn.execute("DELETE FROM conversations WHERE id = ?", (conversation_id,))


# ----------------------------------------------------------------------------
# Messages
# ----------------------------------------------------------------------------
def add_message(conversation_id, role, content, db_path=None):
    now = _now()
    with connect(db_path) as conn:
        cur = conn.execute(
            "INSERT INTO messages (conversation_id, role, content, created_at) VALUES (?, ?, ?, ?)",
            (conversation_id, role, content, now),
        )
        conn.execute("UPDATE conversations SET updated_at = ? WHERE id = ?", (now, conversation_id))
        return cur.lastrowid


def get_messages(conversation_id, limit=None, db_path=None):
    """Return messages oldest-first. If limit is given, return only the last `limit` messages."""
    with connect(db_path) as conn:
        if limit:
            rows = conn.execute(
                "SELECT * FROM (SELECT * FROM messages WHERE conversation_id = ? ORDER BY id DESC LIMIT ?) ORDER BY id ASC",
                (conversation_id, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM messages WHERE conversation_id = ? ORDER BY id ASC", (conversation_id,)
            ).fetchall()
        return [dict(r) for r in rows]


def search_messages(keyword, db_path=None):
    like = f"%{keyword}%"
    with connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT m.conversation_id, c.title, m.role, m.content, m.created_at
            FROM messages m JOIN conversations c ON c.id = m.conversation_id
            WHERE m.content LIKE ?
            ORDER BY m.id DESC LIMIT 20
            """,
            (like,),
        ).fetchall()
        return [dict(r) for r in rows]


def export_conversation_text(conversation_id, db_path=None):
    conv = get_conversation(conversation_id, db_path)
    if not conv:
        return ""
    lines = [f"# {conv['title']}  (id {conv['id']}, created {conv['created_at']})", ""]
    for m in get_messages(conversation_id, db_path=db_path):
        who = {"user": "You", "assistant": "Bot", "system": "System"}[m["role"]]
        lines.append(f"[{m['created_at']}] {who}: {m['content']}")
        lines.append("")
    return "\n".join(lines)
