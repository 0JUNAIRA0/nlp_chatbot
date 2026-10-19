"""
bot.py - Core chatbot logic: Groq API + SQLite memory.

The class is shared by the terminal app (chatbot.py) and the window app (gui.py).
"""

import os

import database as db

DEFAULT_SYSTEM_PROMPT = (
    "You are a friendly, helpful AI assistant. Answer clearly and concisely. "
    "If the user writes in Bangla (Bengali script or Latin letters), reply in the same style."
)

GROQ_DEFAULT_MODEL = "openai/gpt-oss-120b"  # Groq-hosted Llama 3.3 70B
GROQ_BASE_URL = "https://api.groq.com/openai/v1"
HISTORY_LIMIT = 20  # how many past messages are sent to the API each turn


def load_env(path=None):
    """Tiny .env loader (so python-dotenv is not required)."""
    path = path or os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


class _Obj:
    """Tiny attribute-access wrapper so the stdlib client looks like the openai package."""
    def __init__(self, d):
        self._d = d or {}

    def __getattr__(self, name):
        v = self._d.get(name)
        if isinstance(v, dict):
            return _Obj(v)
        if isinstance(v, list):
            return [_Obj(x) if isinstance(x, dict) else x for x in v]
        return v


class _Completions:
    def __init__(self, api_key, base_url):
        self.api_key, self.base_url = api_key, base_url.rstrip("/")

    def create(self, model, messages, stream=True):
        """Call POST /chat/completions with only the standard library (no pip install needed)."""
        import json
        import urllib.error
        import urllib.request

        body = json.dumps({"model": model, "messages": messages, "stream": True}).encode("utf-8")
        req = urllib.request.Request(
            self.base_url + "/chat/completions",
            data=body,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "Accept": "text/event-stream",
                "User-Agent": "nlp-lab-chatbot/1.0",
            },
        )
        try:
            resp = urllib.request.urlopen(req, timeout=60)
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", "ignore")[:300]
            raise RuntimeError(f"API error {e.code}: {detail}") from None
        except urllib.error.URLError as e:
            raise RuntimeError(f"Could not reach the API (check internet): {e.reason}") from None

        def gen():
            with resp:
                for raw in resp:
                    line = raw.decode("utf-8", "ignore").strip()
                    if not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if data == "[DONE]":
                        break
                    try:
                        yield _Obj(json.loads(data))
                    except ValueError:
                        continue

        return gen()


class _Chat:
    def __init__(self, api_key, base_url):
        self.completions = _Completions(api_key, base_url)


class SimpleClient:
    """Minimal Groq API client (OpenAI-compatible endpoint). Uses only the standard library."""
    def __init__(self, api_key, base_url):
        self.base_url = base_url
        self.chat = _Chat(api_key, base_url)


def make_client():
    """Create a Groq client from GROQ_API_KEY. Raises RuntimeError with a clear message."""
    load_env()
    key = (os.environ.get("GROQ_API_KEY") or os.environ.get("OPENAI_API_KEY") or "").strip()
    if not key or key == "your-key-here":
        raise RuntimeError(
            "GROQ_API_KEY not found. Put it in the .env file (GROQ_API_KEY=gsk_...) "
            "or set the GROQ_API_KEY environment variable. Get a key at https://console.groq.com/keys"
        )
    return SimpleClient(key, os.environ.get("GROQ_BASE_URL", GROQ_BASE_URL).strip())


class ChatBot:
    def __init__(self, client=None, model=None, db_path=None):
        load_env()
        self.client = client if client is not None else make_client()
        self.model = model or os.environ.get("GROQ_MODEL") or GROQ_DEFAULT_MODEL
        self.db_path = db_path
        db.init_db(db_path)
        self.conversation_id = None

    # ---- conversation management -------------------------------------------------
    def new_conversation(self, title="New chat"):
        self.conversation_id = db.create_conversation(title, DEFAULT_SYSTEM_PROMPT, self.db_path)
        return self.conversation_id

    def load_conversation(self, conversation_id):
        if not db.get_conversation(conversation_id, self.db_path):
            raise ValueError(f"No conversation with id {conversation_id}")
        self.conversation_id = conversation_id

    def ensure_conversation(self):
        if self.conversation_id is None:
            self.new_conversation()

    @property
    def system_prompt(self):
        conv = db.get_conversation(self.conversation_id, self.db_path)
        return (conv or {}).get("system_prompt") or DEFAULT_SYSTEM_PROMPT

    # ---- chatting ----------------------------------------------------------------
    def _build_messages(self):
        history = db.get_messages(self.conversation_id, limit=HISTORY_LIMIT, db_path=self.db_path)
        msgs = [{"role": "system", "content": self.system_prompt}]
        msgs += [{"role": m["role"], "content": m["content"]} for m in history if m["role"] != "system"]
        return msgs

    def stream_reply(self, user_text):
        """Save the user message, stream the model's answer chunk by chunk, then save the answer."""
        self.ensure_conversation()
        first_message = not db.get_messages(self.conversation_id, limit=1, db_path=self.db_path)
        db.add_message(self.conversation_id, "user", user_text, self.db_path)
        if first_message:
            db.rename_conversation(self.conversation_id, user_text[:40].strip() or "New chat", self.db_path)

        parts = []
        try:
            stream = self.client.chat.completions.create(
                model=self.model, messages=self._build_messages(), stream=True
            )
            for chunk in stream:
                choices = getattr(chunk, "choices", None)
                if not choices:
                    continue
                delta = getattr(choices[0], "delta", None)
                piece = getattr(delta, "content", None)
                if piece:
                    parts.append(piece)
                    yield piece
        finally:
            answer = "".join(parts).strip()
            if answer:
                db.add_message(self.conversation_id, "assistant", answer, self.db_path)

    def reply(self, user_text):
        """Non-streaming convenience wrapper."""
        return "".join(self.stream_reply(user_text))
