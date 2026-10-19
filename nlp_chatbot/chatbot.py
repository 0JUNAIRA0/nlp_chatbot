"""
chatbot.py - Terminal chatbot (Groq API + SQLite database).

Run:  python chatbot.py
"""

import sys

import database as db
from bot import ChatBot

HELP = """Commands:
  /new              start a new conversation
  /list             show all saved conversations
  /load <id>        continue an old conversation
  /rename <title>   rename the current conversation
  /delete <id>      delete a conversation
  /search <word>    search all saved messages
  /system <text>    change the bot's personality for this conversation
  /export           save the current conversation to a .txt file
  /help             show this help
  /quit             exit
"""


def show_history(bot):
    for m in db.get_messages(bot.conversation_id, db_path=bot.db_path):
        who = "You" if m["role"] == "user" else "Bot"
        print(f"{who}: {m['content']}\n")


def handle_command(bot, line):
    cmd, _, arg = line.partition(" ")
    arg = arg.strip()

    if cmd == "/help":
        print(HELP)
    elif cmd == "/new":
        cid = bot.new_conversation()
        print(f"Started new conversation #{cid}.")
    elif cmd == "/list":
        rows = db.list_conversations(bot.db_path)
        if not rows:
            print("No saved conversations yet.")
        for r in rows:
            mark = "*" if r["id"] == bot.conversation_id else " "
            print(f" {mark} #{r['id']:<3} {r['title']:<40} {r['message_count']:>3} msgs  {r['updated_at']}")
    elif cmd == "/load":
        try:
            bot.load_conversation(int(arg))
            print(f"Loaded conversation #{arg}:\n")
            show_history(bot)
        except (ValueError, TypeError) as exc:
            print(f"Could not load: {exc}")
    elif cmd == "/rename":
        if not arg:
            print("Usage: /rename <new title>")
        else:
            bot.ensure_conversation()
            db.rename_conversation(bot.conversation_id, arg, bot.db_path)
            print("Renamed.")
    elif cmd == "/delete":
        try:
            cid = int(arg)
            db.delete_conversation(cid, bot.db_path)
            if cid == bot.conversation_id:
                bot.conversation_id = None
            print(f"Deleted conversation #{cid}.")
        except ValueError:
            print("Usage: /delete <id>")
    elif cmd == "/search":
        if not arg:
            print("Usage: /search <word>")
        else:
            hits = db.search_messages(arg, bot.db_path)
            if not hits:
                print("No matches.")
            for h in hits:
                snippet = h["content"].replace("\n", " ")[:80]
                print(f" #{h['conversation_id']} [{h['role']}] {snippet}")
    elif cmd == "/system":
        if not arg:
            print("Usage: /system <instructions for the bot>")
        else:
            bot.ensure_conversation()
            db.set_system_prompt(bot.conversation_id, arg, bot.db_path)
            print("System prompt updated for this conversation.")
    elif cmd == "/export":
        if bot.conversation_id is None:
            print("Nothing to export yet.")
        else:
            fname = f"conversation_{bot.conversation_id}.txt"
            with open(fname, "w", encoding="utf-8") as f:
                f.write(db.export_conversation_text(bot.conversation_id, bot.db_path))
            print(f"Saved to {fname}")
    elif cmd in ("/quit", "/exit"):
        return False
    else:
        print("Unknown command. Type /help.")
    return True


def main():
    try:
        bot = ChatBot()
    except RuntimeError as exc:
        print(f"Setup problem: {exc}")
        sys.exit(1)

    print("=== NLP Lab Chatbot (Groq + SQLite) ===")
    print(f"Model: {bot.model}   Database: {db.DB_PATH}")
    print("Type /help for commands.\n")

    while True:
        try:
            line = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not line:
            continue
        if line.startswith("/"):
            if not handle_command(bot, line):
                break
            continue

        print("Bot: ", end="", flush=True)
        try:
            for piece in bot.stream_reply(line):
                print(piece, end="", flush=True)
            print("\n")
        except Exception as exc:  # network error, bad key, rate limit ...
            print(f"\n[Error talking to Groq: {exc}]\n")

    print("Goodbye!")


if __name__ == "__main__":
    main()
