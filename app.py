#!/usr/bin/env python3
"""Headlog — personal thought capture system."""

import json
import os
import re
import signal
import socket
import sqlite3
import sys
import threading
from datetime import datetime
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from socketserver import ThreadingMixIn
import urllib.error
import urllib.request
from urllib.parse import parse_qs, urlparse

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
JOURNAL_DIR = DATA_DIR / "journal"
FRONTEND_DIR = BASE_DIR / "frontend"
DB_PATH = DATA_DIR / "thoughts.db"
CONFIG_PATH = DATA_DIR / "config.json"
DEFAULT_CONFIG = {"ai_provider": "ollama", "ai_model": "llama3.2:3b", "api_key": ""}


class ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
    allow_reuse_address = True
    daemon_threads = True


API_PORT = 5959
FRONTEND_PORT = 7777

PRIVATE_TAGS = {"private_todo", "private_reminder"}

VALID_ENRICHMENT_TAGS = {
    "routine", "health", "finance", "idea", "career", "learning", "tech",
    "productivity", "spiritual", "reflection", "gratitude", "vent", "lesson",
    "decision", "question", "todo", "reminder", "people", "selfhelp", "travel",
}

_enrich_semaphore = threading.Semaphore(3)

KEYWORD_MAP = {
    "routine":      ["routine", "morning", "evening", "habit", "wake up", "alarm", "daily", "night", "bedtime", "breakfast", "shower"],
    "health":       ["exercise", "workout", "protein", "sleep", "meditate", "stretch", "doctor", "gym", "calories", "nutrition", "diet", "yoga", "running", "weight", "mental health", "therapy", "anxiety", "headache", "sick", "medicine", "walk"],
    "finance":      ["money", "budget", "invest", "salary", "tax", "crypto", "stock", "spending", "savings", "expense", "income", "portfolio", "mutual fund", "sip", "emi", "rent", "insurance", "retirement", "debt", "credit"],
    "idea":         ["idea", "what if", "brainstorm", "startup", "side project", "launch", "concept", "experiment", "prototype", "build", "create", "invent", "innovation"],
    "career":       ["career", "promotion", "interview", "resume", "leadership", "networking", "job", "role", "manager", "team lead", "performance review", "raise", "skill gap", "linkedin", "corporate", "workplace", "meeting"],
    "learning":     ["learn", "study", "course", "book", "read", "tutorial", "research", "podcast", "article", "lecture", "skill", "certificate", "workshop", "notes", "chapter"],
    "tech":         ["code", "python", "api", "software", "deploy", "bug", "github", "machine learning", "database", "server", "frontend", "backend", "docker", "react", "javascript", "terminal", "linux", "algorithm", "ai", "llm", "model", "app"],
    "productivity": ["productive", "workflow", "optimize", "focus", "deep work", "procrastinate", "time block", "prioritize", "system", "automate", "efficient", "distraction", "pomodoro", "batch", "delegate"],
    "spiritual":    ["spiritual", "mindful", "soul", "purpose", "prayer", "philosophy", "stoic", "presence", "meditation", "consciousness", "faith", "gratitude practice", "inner peace", "universe", "divine", "dharma", "karma"],
    "reflection":   ["reflect", "realize", "notice", "pattern", "insight", "awareness", "tendency", "observe", "looking back", "in hindsight", "it occurs to me", "i see now", "come to think", "self aware"],
    "gratitude":    ["grateful", "thankful", "appreciate", "blessed", "fortunate", "glad", "lucky", "gratitude", "counting blessings"],
    "vent":         ["frustrated", "angry", "sick of", "tired of", "unfair", "disappointed", "annoyed", "hate", "worst", "ridiculous", "can't stand", "pissed", "fed up", "irritated", "overwhelmed", "stressed", "furious"],
    "lesson":       ["lesson", "regret", "mistake", "learned", "never again", "next time", "should have", "could have", "won't repeat", "taught me", "hard way", "wisdom"],
    "decision":     ["decide", "should i", "dilemma", "torn between", "pros and cons", "trade-off", "weighing", "option", "choice", "either", "or should", "alternative", "commit to"],
    "question":     ["wonder", "curious", "how does", "why does", "look up", "research later", "what is", "does anyone", "is it possible", "i want to know", "figure out"],
    "todo":         ["todo", "to-do", "to do", "action item", "follow up", "need to", "have to", "must", "pending", "remember to", "don't forget", "get done", "complete", "finish", "task"],
    "reminder":     ["remind", "meeting", "appointment", "today at", "tomorrow", "deadline", "urgent", "by friday", "by monday", "by end of", "this week", "next week", "at noon", "at night", "schedule", "calendar", "due date", "rsvp", "pickup"],
    "people":       ["met someone", "follow up with", "call", "reach out", "catch up", "friend", "family", "colleague", "introduced", "connection", "relationship", "brother", "sister", "mom", "dad", "girlfriend", "boyfriend", "wife", "husband"],
    "selfhelp":     ["improve", "discipline", "willpower", "growth", "confidence", "accountability", "mindset", "self care", "boundaries", "assertive", "emotional intelligence", "journaling", "affirmation", "visualization", "resilience"],
    "travel":       ["travel", "trip", "vacation", "flight", "bucket list", "adventure", "trek", "hike", "destination", "passport", "visa", "hotel", "airbnb", "itinerary", "explore", "road trip", "backpack"],
}

# Precompile matchers: short single words (≤4 chars) use \b regex,
# longer words and multi-word phrases use substring matching.
_TAG_MATCHERS = {}
for _tag, _keywords in KEYWORD_MAP.items():
    _boundary, _substring = [], []
    for _kw in _keywords:
        if " " not in _kw and len(_kw) <= 4:
            _boundary.append(_kw)
        else:
            _substring.append(_kw.lower())
    _regex = re.compile(
        r"\b(?:" + "|".join(re.escape(w) for w in _boundary) + r")\b",
        re.IGNORECASE,
    ) if _boundary else None
    _TAG_MATCHERS[_tag] = (_regex, _substring)


# ── Auto-tagging ─────────────────────────────────────────────────

def auto_tag(text):
    lower = text.lower()
    tags = []
    for tag, (regex, substrings) in _TAG_MATCHERS.items():
        if regex and regex.search(lower):
            tags.append(tag)
            continue
        if any(kw in lower for kw in substrings):
            tags.append(tag)
    return tags if tags else ["random"]


def merge_tags(manual_tags, auto_tags):
    seen = set()
    merged = []
    for t in manual_tags + auto_tags:
        if t not in seen:
            seen.add(t)
            merged.append(t)
    if any(t != "random" for t in merged):
        merged = [t for t in merged if t != "random"]
    return merged


# ── Database ──────────────────────────────────────────────────────

def get_db():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS thoughts (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            text        TEXT NOT NULL,
            tags        TEXT NOT NULL DEFAULT '[]',
            created_at  TEXT NOT NULL,
            date_key    TEXT NOT NULL,
            word_count  INTEGER NOT NULL DEFAULT 0,
            is_private  INTEGER NOT NULL DEFAULT 0
        )
    """)
    conn.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS thoughts_fts USING fts5(
            text, tags,
            content=thoughts,
            content_rowid=id,
            tokenize='porter unicode61'
        )
    """)
    for trigger in [
        """CREATE TRIGGER IF NOT EXISTS thoughts_ai AFTER INSERT ON thoughts BEGIN
               INSERT INTO thoughts_fts(rowid, text, tags)
               VALUES (new.id, new.text, new.tags);
           END""",
        """CREATE TRIGGER IF NOT EXISTS thoughts_ad AFTER DELETE ON thoughts BEGIN
               INSERT INTO thoughts_fts(thoughts_fts, rowid, text, tags)
               VALUES ('delete', old.id, old.text, old.tags);
           END""",
        """CREATE TRIGGER IF NOT EXISTS thoughts_au AFTER UPDATE ON thoughts BEGIN
               INSERT INTO thoughts_fts(thoughts_fts, rowid, text, tags)
               VALUES ('delete', old.id, old.text, old.tags);
               INSERT INTO thoughts_fts(rowid, text, tags)
               VALUES (new.id, new.text, new.tags);
           END""",
    ]:
        conn.execute(trigger)
    conn.commit()
    conn.close()
    print(f"Database ready: {DB_PATH}")


def _row_to_dict(row):
    d = dict(row)
    d["tags"] = json.loads(d["tags"])
    return d


def save_thought(text, tags_list):
    now = datetime.now()
    created_at = now.strftime("%Y-%m-%dT%H:%M:%S")
    date_key = now.strftime("%Y-%m-%d")
    word_count = len(text.split())
    is_private = 1 if PRIVATE_TAGS & set(tags_list) else 0
    tags_json = json.dumps(tags_list)

    conn = get_db()
    try:
        cur = conn.execute(
            """INSERT INTO thoughts (text, tags, created_at, date_key, word_count, is_private)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (text, tags_json, created_at, date_key, word_count, is_private),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM thoughts WHERE id = ?", (cur.lastrowid,)).fetchone()
        return _row_to_dict(row)
    finally:
        conn.close()


def get_thoughts(limit=50, offset=0, tag=None, date=None):
    clauses, params = [], []

    if tag:
        clauses.append("tags LIKE ?")
        params.append(f'%"{tag}"%')
    if date:
        clauses.append("date_key = ?")
        params.append(date)

    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = f"SELECT * FROM thoughts {where} ORDER BY created_at DESC LIMIT ? OFFSET ?"
    params += [limit, offset]

    conn = get_db()
    try:
        rows = conn.execute(sql, params).fetchall()
        return [_row_to_dict(r) for r in rows]
    finally:
        conn.close()


def search_thoughts(query, limit=50):
    conn = get_db()
    try:
        rows = conn.execute(
            """SELECT t.* FROM thoughts t
               WHERE t.id IN (SELECT rowid FROM thoughts_fts WHERE thoughts_fts MATCH ?)
               ORDER BY t.created_at DESC LIMIT ?""",
            (query, limit),
        ).fetchall()
        return [_row_to_dict(r) for r in rows]
    finally:
        conn.close()


def get_stats():
    conn = get_db()
    try:
        row = conn.execute(
            """SELECT COUNT(*) as total_thoughts,
                      COALESCE(SUM(word_count), 0) as total_words,
                      COUNT(CASE WHEN date_key = ? THEN 1 END) as today_count
               FROM thoughts""",
            (datetime.now().strftime("%Y-%m-%d"),),
        ).fetchone()

        db_size_bytes = DB_PATH.stat().st_size if DB_PATH.exists() else 0
        if db_size_bytes < 1024:
            db_size = f"{db_size_bytes} B"
        elif db_size_bytes < 1024 * 1024:
            db_size = f"{db_size_bytes / 1024:.1f} KB"
        else:
            db_size = f"{db_size_bytes / (1024 * 1024):.1f} MB"

        return {
            "total_thoughts": row["total_thoughts"],
            "total_words": row["total_words"],
            "today_count": row["today_count"],
            "db_size": db_size,
        }
    finally:
        conn.close()


# ── Journal ───────────────────────────────────────────────────────

def write_to_journal(text, tags_list, created_at):
    dt = datetime.strptime(created_at, "%Y-%m-%dT%H:%M:%S")
    year, month, day = dt.strftime("%Y"), dt.strftime("%m"), dt.strftime("%d")
    time_str = dt.strftime("%H:%M:%S")
    full_date = f"{dt.strftime('%A')}, {dt.strftime('%B')} {dt.day}, {dt.year}"

    dir_path = JOURNAL_DIR / year / month
    dir_path.mkdir(parents=True, exist_ok=True)

    file_path = dir_path / f"{year}-{month}-{day}.md"
    tags_str = ", ".join(f"#{t}" for t in tags_list) if tags_list else "#random"
    entry = f"\n### {time_str}  {tags_str}\n{text}\n\n---\n"

    if file_path.exists():
        with open(file_path, "a", encoding="utf-8") as f:
            f.write(entry)
    else:
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(f"# Thoughts — {full_date}\n")
            f.write(entry)


def rebuild_journal_from_db():
    for md_file in JOURNAL_DIR.rglob("*.md"):
        md_file.unlink()

    conn = get_db()
    try:
        rows = conn.execute("SELECT * FROM thoughts ORDER BY created_at ASC").fetchall()
    finally:
        conn.close()

    days = set()
    for row in rows:
        d = _row_to_dict(row)
        days.add(d["date_key"])
        write_to_journal(d["text"], d["tags"], d["created_at"])

    return len(days)


# ── Config ────────────────────────────────────────────────────────

def load_config():
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH, encoding="utf-8") as f:
                return {**DEFAULT_CONFIG, **json.load(f)}
        except Exception:
            pass
    return dict(DEFAULT_CONFIG)


def save_config(config):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)


# ── AI Chat ──────────────────────────────────────────────────────

def check_ollama():
    try:
        req = urllib.request.Request("http://localhost:11434/api/tags")
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status == 200
    except Exception:
        return False


def call_ollama(prompt, model="llama3.2:3b"):
    try:
        data = json.dumps({
            "model": model, "prompt": prompt, "stream": False,
            "options": {"temperature": 0.3, "num_predict": 500},
        }).encode()
        req = urllib.request.Request(
            "http://localhost:11434/api/generate",
            data=data, headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read()).get("response")
    except urllib.error.URLError:
        return None
    except Exception as e:
        print(f"Ollama error: {e}")
        return None


def call_gemini(prompt, model="gemini-2.0-flash-lite", api_key=None):
    if not api_key:
        return None
    try:
        url = (f"https://generativelanguage.googleapis.com/v1beta/"
               f"models/{model}:generateContent?key={api_key}")
        data = json.dumps({
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.3, "maxOutputTokens": 500},
        }).encode()
        req = urllib.request.Request(
            url, data=data, headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read())
            return result["candidates"][0]["content"]["parts"][0]["text"]
    except Exception as e:
        print(f"Gemini error: {e}")
        return None


def build_chat_context(query, limit=30):
    seen, thoughts = set(), []

    try:
        for t in search_thoughts(query, limit=15):
            if t["id"] not in seen:
                seen.add(t["id"])
                thoughts.append(t)
    except Exception:
        pass

    for t in get_thoughts(limit=30):
        if t["id"] not in seen:
            seen.add(t["id"])
            thoughts.append(t)
        if len(thoughts) >= limit:
            break

    lines = []
    for t in thoughts[:limit]:
        tags_str = ", ".join(f"#{tag}" for tag in t["tags"])
        time_part = t["created_at"].split("T")[1] if "T" in t["created_at"] else ""
        lines.append(f"[{t['date_key']} {time_part}] {tags_str} — {t['text']}")

    return "\n".join(lines)


def build_chat_prompt(user_message, context):
    return f"""You are a personal thought assistant. The user logs their thoughts, ideas, reminders, reflections, and tasks throughout the day. Below are their recent thoughts for context.

YOUR ROLE:
- Answer questions about the user's thoughts by referencing the actual entries below
- Summarize, find patterns, list items, and recall specific thoughts
- If asked about something not in the thoughts, say you don't see any entries about that topic
- Be concise and direct — no filler, no motivational fluff
- Reference specific dates and times when relevant
- Never invent or hallucinate thoughts that aren't in the context below

USER'S THOUGHTS:
{context}

USER'S QUESTION: {user_message}"""


# ── AI Tag Enrichment (Layer 3) ──────────────────────────────────

def _call_ai_classify(prompt, config):
    provider = config.get("ai_provider", "ollama")
    model = config.get("ai_model", "llama3.2:3b")

    if provider == "gemini":
        api_key = config.get("api_key", "")
        if not api_key:
            return None
        try:
            url = (f"https://generativelanguage.googleapis.com/v1beta/"
                   f"models/{model}:generateContent?key={api_key}")
            data = json.dumps({
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": 0.1, "maxOutputTokens": 50},
            }).encode()
            req = urllib.request.Request(
                url, data=data, headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                result = json.loads(resp.read())
                return result["candidates"][0]["content"]["parts"][0]["text"]
        except Exception:
            return None

    try:
        data = json.dumps({
            "model": model, "prompt": prompt, "stream": False,
            "options": {"temperature": 0.1, "num_predict": 50},
        }).encode()
        req = urllib.request.Request(
            "http://localhost:11434/api/generate",
            data=data, headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read()).get("response")
    except Exception:
        return None


def update_journal_tags(date_key, created_at, new_tags):
    try:
        dt = datetime.strptime(created_at, "%Y-%m-%dT%H:%M:%S")
        year, month, day = dt.strftime("%Y"), dt.strftime("%m"), dt.strftime("%d")
        time_str = dt.strftime("%H:%M:%S")

        file_path = JOURNAL_DIR / year / month / f"{year}-{month}-{day}.md"
        if not file_path.exists():
            return

        content = file_path.read_text(encoding="utf-8")
        tags_str = ", ".join(f"#{t}" for t in new_tags)
        pattern = rf"(### {re.escape(time_str)}  )#[^\n]+"
        updated = re.sub(pattern, rf"\g<1>{tags_str}", content, count=1)

        if updated != content:
            file_path.write_text(updated, encoding="utf-8")
    except Exception:
        pass


def ai_enrich_tags(thought_id, text, existing_tags, date_key, created_at):
    if not _enrich_semaphore.acquire(blocking=False):
        return
    try:
        config = load_config()
        provider = config.get("ai_provider", "ollama")
        if provider == "none":
            return
        if provider == "gemini" and not config.get("api_key"):
            return

        existing_str = ", ".join(existing_tags) if existing_tags else "none"
        prompt = (
            "You are a tag classifier. Given a personal thought entry, "
            "suggest which tags apply from this EXACT list and no others:\n\n"
            "routine, health, finance, idea, career, learning, tech, "
            "productivity, spiritual, reflection, gratitude, vent, lesson, "
            "decision, question, todo, reminder, people, selfhelp, travel\n\n"
            "Rules:\n"
            "- Return ONLY tag names from the list above, comma-separated, nothing else\n"
            "- Suggest 1-3 tags that capture the MEANING, not just keywords\n"
            f"- Do NOT suggest tags that are already applied: {existing_str}\n"
            "- Do NOT suggest: private_todo, private_reminder, random\n"
            "- If no additional tags are needed, return: none\n\n"
            f'Thought: "{text}"\n\n'
            "Tags:"
        )

        raw = _call_ai_classify(prompt, config)
        if not raw:
            return

        candidates = [t.strip().lower() for t in raw.split(",")]
        existing_set = set(existing_tags)
        new_ai_tags = [
            t for t in candidates
            if t in VALID_ENRICHMENT_TAGS and t not in existing_set
        ]
        if not new_ai_tags:
            return

        merged = list(existing_tags) + new_ai_tags
        if any(t != "random" for t in merged):
            merged = [t for t in merged if t != "random"]

        tags_json = json.dumps(merged)
        is_private = 1 if PRIVATE_TAGS & set(merged) else 0

        conn = get_db()
        try:
            conn.execute(
                "UPDATE thoughts SET tags = ?, is_private = ? WHERE id = ?",
                (tags_json, is_private, thought_id),
            )
            conn.commit()
        finally:
            conn.close()

        update_journal_tags(date_key, created_at, merged)
        print(f"Enriched thought {thought_id}: +{new_ai_tags}")

    except Exception as e:
        print(f"Enrichment error for thought {thought_id}: {e}")
    finally:
        _enrich_semaphore.release()


def maybe_enrich(thought):
    if thought.get("word_count", 0) < 5:
        return
    if len(thought.get("tags", [])) >= 4:
        return

    config = load_config()
    provider = config.get("ai_provider", "ollama")
    if provider == "none":
        return
    if provider == "gemini" and not config.get("api_key"):
        return

    threading.Thread(
        target=ai_enrich_tags,
        args=(thought["id"], thought["text"], thought["tags"],
              thought["date_key"], thought["created_at"]),
        daemon=True,
    ).start()


# ── Frontend server (static files on :7777) ──────────────────────

class FrontendHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(FRONTEND_DIR), **kwargs)

    def do_GET(self):
        if urlparse(self.path).path == "/":
            self.path = "/index.html"
        return super().do_GET()

    def log_message(self, format, *args):
        pass


# ── API server (JSON endpoints on :5959) ─────────────────────────

class APIHandler(SimpleHTTPRequestHandler):

    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        qs = parse_qs(parsed.query)

        if path == "/api/thoughts":
            try:
                rows = get_thoughts(
                    limit=int(qs.get("limit", [50])[0]),
                    offset=int(qs.get("offset", [0])[0]),
                    tag=qs.get("tag", [None])[0],
                    date=qs.get("date", [None])[0],
                )
                return self._json_response(rows)
            except Exception as e:
                return self._json_response({"error": str(e)}, 500)

        if path == "/api/search":
            q = qs.get("q", [""])[0]
            if not q:
                return self._json_response([])
            try:
                return self._json_response(search_thoughts(q, limit=int(qs.get("limit", [50])[0])))
            except Exception as e:
                return self._json_response({"error": str(e)}, 500)

        if path == "/api/stats":
            try:
                return self._json_response(get_stats())
            except Exception as e:
                return self._json_response({"error": str(e)}, 500)

        if path == "/api/config":
            return self._json_response(load_config())

        if path == "/api/health":
            return self._json_response({"ollama": check_ollama()})

        if path.startswith("/api/thoughts/"):
            try:
                thought_id = int(path.split("/")[-1])
                conn = get_db()
                try:
                    row = conn.execute(
                        "SELECT * FROM thoughts WHERE id = ?", (thought_id,)
                    ).fetchone()
                finally:
                    conn.close()
                if row:
                    return self._json_response(_row_to_dict(row))
                return self._json_response({"error": "not found"}, 404)
            except Exception as e:
                return self._json_response({"error": str(e)}, 500)

        self.send_error(404)

    def do_POST(self):
        path = urlparse(self.path).path

        if path == "/api/thoughts":
            try:
                body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
                text = body.get("text", "").strip()
                if not text:
                    return self._json_response({"error": "text is required"}, 400)
                manual_tags = body.get("tags", [])
                detected = auto_tag(text)
                final_tags = merge_tags(manual_tags, detected)
                thought = save_thought(text, final_tags)
                try:
                    write_to_journal(text, final_tags, thought["created_at"])
                except Exception as je:
                    print(f"Journal write failed: {je}")
                self._json_response({
                    "thought": thought,
                    "auto_tags": [t for t in detected if t != "random"],
                    "manual_tags": manual_tags,
                }, 201)
                maybe_enrich(thought)
                return
            except Exception as e:
                return self._json_response({"error": str(e)}, 500)

        if path == "/api/rebuild-journal":
            try:
                days = rebuild_journal_from_db()
                return self._json_response({"status": "ok", "days_rebuilt": days})
            except Exception as e:
                return self._json_response({"error": str(e)}, 500)

        if path == "/api/chat":
            try:
                body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
                message = body.get("message", "").strip()
                if not message:
                    return self._json_response({"error": "message is required"}, 400)

                config = load_config()
                provider = config.get("ai_provider", "ollama")
                model = config.get("ai_model", "llama3.2:3b")

                if provider == "none":
                    return self._json_response({
                        "response": "AI chat is disabled. Enable it in Settings.",
                        "status": "disabled",
                    })

                context = build_chat_context(message)
                prompt = build_chat_prompt(message, context)
                context_count = context.count("\n") + 1 if context else 0

                if provider == "gemini":
                    result = call_gemini(prompt, model, config.get("api_key", ""))
                else:
                    result = call_ollama(prompt, model)

                if result is None:
                    hint = ("Ollama is not running. Start it with "
                            "'ollama serve' in a terminal, then try again."
                            if provider == "ollama"
                            else f"Could not reach {provider}. Check your API key and try again.")
                    return self._json_response({"response": hint, "status": "error"})

                return self._json_response({
                    "response": result, "status": "ok",
                    "model": model, "context_count": context_count,
                })
            except Exception as e:
                return self._json_response({"error": str(e)}, 500)

        if path == "/api/config":
            try:
                body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
                config = load_config()
                config.update(body)
                save_config(config)
                return self._json_response({"status": "ok"})
            except Exception as e:
                return self._json_response({"error": str(e)}, 500)

        self.send_error(404)

    def _json_response(self, data, status=200):
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        pass


# ── Startup ───────────────────────────────────────────────────────

def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def main():
    DATA_DIR.mkdir(exist_ok=True)
    JOURNAL_DIR.mkdir(exist_ok=True)
    init_db()

    host = "0.0.0.0"
    api_server = ThreadingHTTPServer((host, API_PORT), APIHandler)
    frontend_server = ThreadingHTTPServer((host, FRONTEND_PORT), FrontendHandler)

    def shutdown(sig, frame):
        print("\nShutting down...")
        api_server.shutdown()
        frontend_server.shutdown()
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    threading.Thread(target=api_server.serve_forever, daemon=True).start()

    local_ip = get_local_ip()
    print(f"Headlog running on http://localhost:{FRONTEND_PORT}")
    print(f"API server on http://localhost:{API_PORT}")
    print(f"iPhone access: http://{local_ip}:{FRONTEND_PORT}")

    frontend_server.serve_forever()


if __name__ == "__main__":
    main()
