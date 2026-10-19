"""
gui.py - Window chatbot (Tkinter) with a conversation sidebar stored in SQLite.

Run:  python gui.py
"""

import queue
import threading
import tkinter as tk
from tkinter import messagebox, scrolledtext, simpledialog

import database as db
from bot import ChatBot

BG, PANEL, FG = "#1e1f26", "#2a2c36", "#f0f0f0"


class App:
    def __init__(self, root, bot):
        self.root, self.bot = root, bot
        self.q = queue.Queue()
        self.busy = False
        self.conv_ids = []

        root.title("NLP Lab Chatbot - Groq + SQLite")
        root.geometry("900x620")
        root.configure(bg=BG)

        # sidebar
        side = tk.Frame(root, bg=PANEL, width=240)
        side.pack(side=tk.LEFT, fill=tk.Y)
        side.pack_propagate(False)
        tk.Button(side, text="+ New chat", command=self.new_chat, bg="#4f8cff", fg="white", bd=0,
                  pady=8).pack(fill=tk.X, padx=8, pady=8)
        self.listbox = tk.Listbox(side, bg=PANEL, fg=FG, bd=0, highlightthickness=0,
                                  selectbackground="#4f8cff", activestyle="none")
        self.listbox.pack(fill=tk.BOTH, expand=True, padx=8)
        self.listbox.bind("<<ListboxSelect>>", self.on_select)
        row = tk.Frame(side, bg=PANEL)
        row.pack(fill=tk.X, padx=8, pady=8)
        tk.Button(row, text="Rename", command=self.rename_chat, bd=0).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 4))
        tk.Button(row, text="Delete", command=self.delete_chat, bd=0).pack(side=tk.LEFT, expand=True, fill=tk.X)

        # chat area
        main = tk.Frame(root, bg=BG)
        main.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.chat = scrolledtext.ScrolledText(main, wrap=tk.WORD, state="disabled", bg=PANEL, fg=FG,
                                              font=("Segoe UI", 11), bd=0, padx=12, pady=12)
        self.chat.pack(fill=tk.BOTH, expand=True, padx=10, pady=(10, 5))
        self.chat.tag_config("user", foreground="#7fd1ff", spacing1=8)
        self.chat.tag_config("bot", foreground="#b6f5a8", spacing1=8)
        self.chat.tag_config("err", foreground="#ff8080", spacing1=8)

        bottom = tk.Frame(main, bg=BG)
        bottom.pack(fill=tk.X, padx=10, pady=(0, 10))
        self.entry = tk.Entry(bottom, font=("Segoe UI", 12), bg=PANEL, fg=FG, insertbackground="white", bd=0)
        self.entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=8, padx=(0, 8))
        self.entry.bind("<Return>", self.send)
        self.entry.focus()
        self.send_btn = tk.Button(bottom, text="Send", command=self.send, bg="#4f8cff", fg="white",
                                  bd=0, padx=16, pady=6)
        self.send_btn.pack(side=tk.RIGHT)

        self.refresh_list()
        self.append("bot", "Hi! Ask me anything. Your chats are saved in the sidebar.\n")
        self.root.after(50, self.poll)

    # ---- helpers ---------------------------------------------------------------
    def append(self, tag, text):
        self.chat.config(state="normal")
        self.chat.insert(tk.END, text, tag)
        self.chat.config(state="disabled")
        self.chat.see(tk.END)

    def refresh_list(self):
        self.listbox.delete(0, tk.END)
        rows = db.list_conversations(self.bot.db_path)
        self.conv_ids = [r["id"] for r in rows]
        for r in rows:
            self.listbox.insert(tk.END, f"{r['title']}")
        if self.bot.conversation_id in self.conv_ids:
            idx = self.conv_ids.index(self.bot.conversation_id)
            self.listbox.selection_set(idx)

    def show_conversation(self):
        self.chat.config(state="normal")
        self.chat.delete("1.0", tk.END)
        self.chat.config(state="disabled")
        for m in db.get_messages(self.bot.conversation_id, db_path=self.bot.db_path):
            if m["role"] == "user":
                self.append("user", f"You: {m['content']}\n")
            else:
                self.append("bot", f"Bot: {m['content']}\n")

    # ---- sidebar actions -------------------------------------------------------
    def new_chat(self):
        if self.busy:
            return
        self.bot.new_conversation()
        self.show_conversation()
        self.refresh_list()

    def on_select(self, _):
        if self.busy:
            return
        sel = self.listbox.curselection()
        if not sel:
            return
        self.bot.load_conversation(self.conv_ids[sel[0]])
        self.show_conversation()

    def rename_chat(self):
        if self.bot.conversation_id is None:
            return
        title = simpledialog.askstring("Rename", "New title:", parent=self.root)
        if title:
            db.rename_conversation(self.bot.conversation_id, title, self.bot.db_path)
            self.refresh_list()

    def delete_chat(self):
        if self.bot.conversation_id is None:
            return
        if messagebox.askyesno("Delete", "Delete this conversation permanently?"):
            db.delete_conversation(self.bot.conversation_id, self.bot.db_path)
            self.bot.conversation_id = None
            self.show_conversation_empty()
            self.refresh_list()

    def show_conversation_empty(self):
        self.chat.config(state="normal")
        self.chat.delete("1.0", tk.END)
        self.chat.config(state="disabled")

    # ---- sending ---------------------------------------------------------------
    def send(self, _=None):
        text = self.entry.get().strip()
        if not text or self.busy:
            return
        self.entry.delete(0, tk.END)
        self.busy = True
        self.send_btn.config(state="disabled")
        self.append("user", f"You: {text}\n")
        self.append("bot", "Bot: ")
        threading.Thread(target=self.worker, args=(text,), daemon=True).start()

    def worker(self, text):
        try:
            for piece in self.bot.stream_reply(text):
                self.q.put(("piece", piece))
            self.q.put(("done", None))
        except Exception as exc:
            self.q.put(("error", str(exc)))

    def poll(self):
        try:
            while True:
                kind, data = self.q.get_nowait()
                if kind == "piece":
                    self.append("bot", data)
                elif kind == "done":
                    self.append("bot", "\n")
                    self.finish()
                else:
                    self.append("err", f"\n[Error: {data}]\n")
                    self.finish()
        except queue.Empty:
            pass
        self.root.after(50, self.poll)

    def finish(self):
        self.busy = False
        self.send_btn.config(state="normal")
        self.refresh_list()


def main():
    try:
        bot = ChatBot()
    except RuntimeError as exc:
        r = tk.Tk()
        r.withdraw()
        messagebox.showerror("Setup problem", str(exc))
        return
    root = tk.Tk()
    App(root, bot)
    root.mainloop()


if __name__ == "__main__":
    main()
