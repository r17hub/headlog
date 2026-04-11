#!/usr/bin/env python3
"""Headlog — personal thought capture system."""

import calendar
import json
import mimetypes
import os
import re
import signal
import socket
import sqlite3
import subprocess
import sys
import threading
import time
from datetime import datetime, timedelta
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from socketserver import ThreadingMixIn
import urllib.error
import urllib.request
from urllib.parse import parse_qs, urlparse

from alarm_engine import (
    DEFAULT_ALARM_CONFIG,
    generate_alarm_sequence,
    parse_time_signal,
)

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
JOURNAL_DIR = DATA_DIR / "journal"
FRONTEND_DIR = BASE_DIR / "frontend"
SFX_DIR = BASE_DIR / "assets" / "sfx"
DB_PATH = DATA_DIR / "thoughts.db"
CONFIG_PATH = DATA_DIR / "config.json"
DEFAULT_CONFIG = {
    "ai_provider": "ollama",
    "ai_model": "llama3.2:3b",
    "api_key": "",
    "alarms": DEFAULT_ALARM_CONFIG,
}


class ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
    allow_reuse_address = True
    daemon_threads = True


API_PORT = 5959
FRONTEND_PORT = 7777

PRIVATE_TAGS = {"private_todo", "private_reminder"}

VALID_PRIORITIES = {"p0", "p1", "p2"}
_PRIORITY_INLINE_RE = re.compile(r'#(p[0-2])\b', re.IGNORECASE)


def extract_priority(text, manual_tags=None, body_priority=None):
    """Extract priority from all input sources. Returns (cleaned_text, priority).

    Priority resolution order (first wins):
    1. Inline #p0/#p1/#p2 in thought text
    2. body_priority field from POST body (chip selection)
    3. #p0/#p1/#p2 found in manual_tags array
    4. None
    """
    priority = None
    cleaned_text = text

    match = _PRIORITY_INLINE_RE.search(text)
    if match:
        priority = match.group(1).lower()
        cleaned_text = _PRIORITY_INLINE_RE.sub('', text).strip()
        cleaned_text = re.sub(r'  +', ' ', cleaned_text)

    if not priority and body_priority:
        bp = str(body_priority).lower().strip()
        if bp in VALID_PRIORITIES:
            priority = bp

    if not priority and manual_tags:
        for tag in manual_tags:
            if tag.lower() in VALID_PRIORITIES:
                priority = tag.lower()
                break

    return cleaned_text, priority


def strip_priority_from_tags(tags_list):
    """Remove any p0/p1/p2 entries from a tags list."""
    return [t for t in tags_list if t.lower() not in VALID_PRIORITIES]


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
    "todo":         ["todo", "to-do", "to do", "action item", "follow up", "need to", "have to", "must", "pending", "remember to", "don't forget", "get done", "complete", "finish", "task", "reply to", "respond to", "get back to", "look into", "take care", "work on", "deal with", "sort out", "set up", "clean up", "wrap up", "fill out", "sign up", "make sure"],
    "reminder":     ["remind", "meeting", "appointment", "today at", "tomorrow", "deadline", "urgent", "by friday", "by monday", "by end of", "this week", "next week", "at noon", "at night", "schedule", "calendar", "due date", "rsvp", "pickup", "by today", "by tonight", "by tomorrow", "by eod", "end of day", "before tomorrow"],
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


# ── Imperative-verb detection ────────────────────────────────────
# When the first word is a bare action verb ("Reply …", "Send …", "Fix …"),
# the thought is almost certainly a task.
_IMPERATIVE_VERBS = {
    "add", "apply", "approve", "arrange", "ask", "assign", "attend",
    "book", "buy",
    "call", "cancel", "check", "clean", "close", "collect", "confirm",
    "contact", "coordinate", "create",
    "debug", "delegate", "deliver", "deploy", "discuss", "download",
    "draft", "drop",
    "edit", "email", "escalate",
    "fill", "finalize", "fix", "follow", "forward",
    "get", "give",
    "handle",
    "implement", "inform", "install", "investigate",
    "join",
    "look",
    "make", "meet", "merge", "message", "move",
    "notify",
    "order", "organize",
    "pay", "pick", "ping", "plan", "post", "prepare", "print",
    "proofread", "publish", "push", "put",
    "reach", "register", "remove", "renew", "replace", "reply",
    "report", "request", "reschedule", "resolve", "respond", "return",
    "review", "revise",
    "save", "schedule", "send", "set", "setup", "share", "ship",
    "sign", "sort", "start", "submit", "switch",
    "take", "tell", "test", "text", "transfer",
    "update", "upgrade", "upload",
    "verify", "visit",
    "watch", "withdraw", "wrap", "write",
}

# ── Deadline-pattern detection ───────────────────────────────────
_DEADLINE_RE = re.compile(
    r"\b(?:"
    r"by\s+(?:today|tonight|tomorrow|eod|end\s+of\s+(?:day|week)|"
    r"monday|tuesday|wednesday|thursday|friday|saturday|sunday)"
    r"|before\s+(?:tomorrow|end\s+of|monday|tuesday|wednesday|"
    r"thursday|friday|saturday|sunday)"
    r"|due\s+(?:today|tomorrow|by|on|before)"
    r"|asap|as\s+soon\s+as\s+possible"
    r")\b",
    re.IGNORECASE,
)


# ── Auto-tagging ─────────────────────────────────────────────────

def auto_tag(text):
    lower = text.lower()
    tags = []

    # Layer 1: keyword / substring matching
    for tag, (regex, substrings) in _TAG_MATCHERS.items():
        if regex and regex.search(lower):
            tags.append(tag)
            continue
        if any(kw in lower for kw in substrings):
            tags.append(tag)

    # Layer 2: imperative first-word → todo
    # Skip if reminder already matched — the verb is part of reminder phrasing
    # (e.g. "set me a reminder", "schedule a meeting")
    words = lower.split()
    if words and words[0] in _IMPERATIVE_VERBS and "todo" not in tags and "reminder" not in tags:
        tags.append("todo")

    # Layer 3: deadline phrase → todo
    # Skip if reminder already matched — deadline reinforces the reminder, not a separate task
    if _DEADLINE_RE.search(lower) and "todo" not in tags and "reminder" not in tags:
        tags.append("todo")

    return tags if tags else ["random"]


def _allow_ai_action_tags(text):
    """Only allow AI to add todo/reminder when intent signals exist."""
    detected = auto_tag(text or "")
    if "todo" in detected or "reminder" in detected:
        return True

    parsed = parse_time_signal(
        text or "",
        now=datetime.now(),
        config=get_alarm_config(),
    )
    return parsed.get("zone") != "open_todo"


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
    conn.execute("PRAGMA foreign_keys=ON")
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

    # ── Schema migrations ────────────────────────────────────────────
    cursor = conn.execute("PRAGMA table_info(thoughts)")
    columns = [row[1] for row in cursor.fetchall()]
    if 'edited_at' not in columns:
        conn.execute("ALTER TABLE thoughts ADD COLUMN edited_at TEXT DEFAULT NULL")
    if 'status' not in columns:
        conn.execute("ALTER TABLE thoughts ADD COLUMN status TEXT NOT NULL DEFAULT 'active'")
    if 'priority' not in columns:
        conn.execute("ALTER TABLE thoughts ADD COLUMN priority TEXT DEFAULT NULL")
    if 'is_muted' not in columns:
        conn.execute("ALTER TABLE thoughts ADD COLUMN is_muted INTEGER NOT NULL DEFAULT 0")
    if 'emoji' not in columns:
        conn.execute("ALTER TABLE thoughts ADD COLUMN emoji TEXT DEFAULT NULL")

    # ── Edit history audit log (append-only) ───────────────────────
    conn.execute("""
        CREATE TABLE IF NOT EXISTS thought_edits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            thought_id INTEGER NOT NULL,
            old_text TEXT NOT NULL,
            new_text TEXT NOT NULL,
            old_tags TEXT NOT NULL,
            new_tags TEXT NOT NULL,
            edited_at TEXT NOT NULL,
            FOREIGN KEY (thought_id) REFERENCES thoughts(id) ON DELETE CASCADE
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_edits_thought ON thought_edits(thought_id)")

    # ── Alarm table ─────────────────────────────────────────────────
    conn.execute("""
        CREATE TABLE IF NOT EXISTS alarms (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            thought_id INTEGER NOT NULL,
            zone TEXT NOT NULL,
            sequence_index INTEGER NOT NULL,
            fire_at TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            tone TEXT NOT NULL,
            message TEXT NOT NULL,
            snoozed_until TEXT,
            snooze_count INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            FOREIGN KEY (thought_id) REFERENCES thoughts(id) ON DELETE CASCADE
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_alarms_pending ON alarms(fire_at) WHERE status = 'pending'"
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_alarms_thought ON alarms(thought_id)")

    # ── Routines tables ──────────────────────────────────────────
    conn.execute("""
        CREATE TABLE IF NOT EXISTS routines (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            thought_id INTEGER,
            title TEXT NOT NULL,
            schedule_type TEXT NOT NULL,
            schedule_data TEXT NOT NULL DEFAULT '{}',
            status TEXT NOT NULL DEFAULT 'active',
            created_at TEXT NOT NULL,
            paused_at TEXT,
            archived_at TEXT,
            FOREIGN KEY (thought_id) REFERENCES thoughts(id) ON DELETE SET NULL
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_routines_status ON routines(status)")

    conn.execute("""
        CREATE TABLE IF NOT EXISTS routine_completions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            routine_id INTEGER NOT NULL,
            completed_date TEXT NOT NULL,
            completed_at TEXT NOT NULL,
            FOREIGN KEY (routine_id) REFERENCES routines(id) ON DELETE CASCADE,
            UNIQUE(routine_id, completed_date)
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_rc_routine_date ON routine_completions(routine_id, completed_date)")

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

    # ── Notification events table ─────────────────────────────────
    conn.execute("""
        CREATE TABLE IF NOT EXISTS notification_events (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            message    TEXT NOT NULL,
            type       TEXT NOT NULL DEFAULT 'alarm',
            thought_id INTEGER,
            fired_at   TEXT NOT NULL,
            is_read    INTEGER NOT NULL DEFAULT 0
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_notif_fired ON notification_events(fired_at)"
    )

    conn.commit()
    conn.close()
    print(f"Database ready: {DB_PATH}")


def _row_to_dict(row):
    d = dict(row)
    d["tags"] = json.loads(d["tags"])
    d.setdefault("priority", None)
    d["is_muted"] = bool(d.get("is_muted", 0))
    d.setdefault("emoji", None)
    return d


def save_thought(text, tags_list, priority=None):
    now = datetime.now()
    created_at = now.strftime("%Y-%m-%dT%H:%M:%S")
    date_key = now.strftime("%Y-%m-%d")
    word_count = len(text.split())
    is_private = 1 if PRIVATE_TAGS & set(tags_list) else 0
    tags_json = json.dumps(tags_list)

    conn = get_db()
    try:
        cur = conn.execute(
            """INSERT INTO thoughts (text, tags, created_at, date_key, word_count, is_private, priority)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (text, tags_json, created_at, date_key, word_count, is_private, priority),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM thoughts WHERE id = ?", (cur.lastrowid,)).fetchone()
        return _row_to_dict(row)
    finally:
        conn.close()


TONE_TO_FILE = {
    "gentle": "tone-gentle.mp3",
    "warm": "tone-warm.mp3",
    "firm": "tone-firm.mp3",
    "urgent": "tone-urgent.mp3",
    "sharp": "tone-sharp.mp3",
}

NOTIFICATION_RESHOW_DELAYS = (7, 14)


def play_sound(tone):
    """Play alarm tone using afplay (macOS built-in)."""
    cfg = get_alarm_config()
    if not cfg.get("sounds_enabled", True):
        return

    try:
        filename = TONE_TO_FILE.get(tone, "tone-gentle.mp3")
        filepath = SFX_DIR / filename
        if filepath.exists():
            subprocess.Popen(
                ["afplay", str(filepath)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
    except Exception as err:
        print(f"Sound playback failed: {err}")


def _normalize_notification_text(title, message):
    # Normalize text so Notification Center gets concise banner content.
    safe_title = " ".join((title or "").split()).strip() or "Headlog"
    safe_message = " ".join((message or "").split()).strip() or "Reminder"
    if len(safe_title) > 72:
        safe_title = safe_title[:69].rstrip() + "..."
    if len(safe_message) > 220:
        safe_message = safe_message[:217].rstrip() + "..."
    return safe_title, safe_message


def _send_macos_notification(title, message):
    try:
        script_lines = [
            "on run argv",
            "set noteBody to item 1 of argv",
            "set noteTitle to item 2 of argv",
            'display notification noteBody with title noteTitle subtitle "Headlog"',
            "end run",
        ]
        cmd = ["osascript"]
        for line in script_lines:
            cmd.extend(["-e", line])
        cmd.extend(["--", message, title])

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode != 0:
            err = (result.stderr or result.stdout or "").strip()
            print(f"Notification failed (osascript): {err or 'unknown error'}")
            return False
        return True
    except Exception as err:
        print(f"Notification failed: {err}")
        return False


def _reshow_notification(title, message):
    """Re-show macOS banners over ~20s so reminders are harder to miss."""
    start = time.time()
    for target_second in NOTIFICATION_RESHOW_DELAYS:
        wait_for = target_second - (time.time() - start)
        if wait_for > 0:
            time.sleep(wait_for)
        _send_macos_notification(title, message)


def _record_notification(message, notif_type='alarm', thought_id=None):
    """Insert a notification event row (non-fatal; never raises)."""
    try:
        conn = get_db()
        try:
            conn.execute(
                "INSERT INTO notification_events (message, type, thought_id, fired_at) VALUES (?, ?, ?, ?)",
                (message, notif_type, thought_id, datetime.now().strftime("%Y-%m-%dT%H:%M:%S")),
            )
            conn.commit()
        finally:
            conn.close()
    except Exception as err:
        print(f"[Notification] record failed: {err}")


def fire_notification(title, message, tone="gentle", thought_id=None, notif_type='alarm'):
    """Fire visual notification and play the requested tone."""
    play_sound(tone)
    safe_title, safe_message = _normalize_notification_text(title, message)
    delivered = _send_macos_notification(safe_title, safe_message)
    if delivered and NOTIFICATION_RESHOW_DELAYS:
        threading.Thread(
            target=_reshow_notification,
            args=(safe_title, safe_message),
            daemon=True,
        ).start()
    combined = f"{safe_title} \u2014 {safe_message}" if safe_title != safe_message else safe_message
    _record_notification(combined, notif_type, thought_id)


def _alarms_table_exists(conn):
    exists = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='alarms'"
    ).fetchone()
    return bool(exists)


def cancel_pending_alarms(conn, thought_id):
    if not _alarms_table_exists(conn):
        return
    conn.execute(
        "UPDATE alarms SET status = 'cancelled' WHERE thought_id = ? AND status = 'pending'",
        (thought_id,),
    )


def insert_alarms_for_thought(thought_id, text, tags_list, created_at):
    alarm_tags = {"reminder", "todo", "private_reminder", "private_todo"}
    if not alarm_tags.intersection(set(tags_list)):
        return 0, None

    now = datetime.now()
    parsed = parse_time_signal(text, now=now, config=get_alarm_config())
    created_dt = datetime.strptime(created_at, "%Y-%m-%dT%H:%M:%S")
    is_private = bool({"private_reminder", "private_todo"}.intersection(set(tags_list)))

    alarms = generate_alarm_sequence(
        parsed,
        text,
        now=now,
        config=get_alarm_config(),
        created_at=created_dt,
        is_private=is_private,
    )
    if not alarms:
        return 0, parsed["zone"]

    conn = get_db()
    try:
        now_iso = now.isoformat()
        for alarm in alarms:
            conn.execute(
                "INSERT INTO alarms (thought_id, zone, sequence_index, fire_at, tone, message, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    thought_id,
                    alarm["zone"],
                    alarm["sequence_index"],
                    alarm["fire_at"],
                    alarm["tone"],
                    alarm["message"],
                    now_iso,
                ),
            )
        conn.commit()
    finally:
        conn.close()

    return len(alarms), parsed["zone"]


def _get_pending_alarm_counts(thought_ids):
    if not thought_ids:
        return {}

    conn = get_db()
    try:
        if not _alarms_table_exists(conn):
            return {}
        placeholders = ",".join("?" for _ in thought_ids)
        rows = conn.execute(
            f"SELECT thought_id, COUNT(*) AS cnt FROM alarms "
            f"WHERE status = 'pending' AND thought_id IN ({placeholders}) "
            f"GROUP BY thought_id",
            thought_ids,
        ).fetchall()
        return {row["thought_id"]: row["cnt"] for row in rows}
    finally:
        conn.close()


def _compute_deadline_label(zone, anchor, now):
    """Compute a human-readable deadline string."""
    if not anchor:
        if zone == "open_todo":
            return "open task"
        return None

    anchor_dt = anchor if isinstance(anchor, datetime) else datetime.fromisoformat(str(anchor))
    today = now.date()
    tomorrow = today + timedelta(days=1)
    anchor_date = anchor_dt.date()

    hour = anchor_dt.hour
    minute = anchor_dt.minute

    if hour == 23 and minute == 59:
        time_part = "end of day"
    elif minute != 0:
        time_part = anchor_dt.strftime("%-I:%M %p").lower()
    else:
        time_part = anchor_dt.strftime("%-I %p").lower()

    if anchor_date == today:
        if zone == "pinned":
            return f"by {time_part}"
        if zone == "day_bound":
            return "by end of today"
        return f"by {time_part} today"

    if anchor_date == tomorrow:
        if zone == "pinned":
            return f"by {time_part} tomorrow"
        return "by tomorrow"

    days_away = (anchor_date - today).days
    if 2 <= days_away <= 6:
        day_name = anchor_dt.strftime("%A")
        if zone == "pinned":
            return f"by {time_part}, {day_name}"
        return f"by {day_name}"

    return f"by {anchor_dt.strftime('%b %-d')}"


def _time_greeting(now):
    """Return time-of-day greeting key."""
    hour = now.hour
    if hour < 12:
        return "morning"
    if hour < 17:
        return "afternoon"
    return "evening"


def _compute_urgency_tier(time_remaining_seconds, urgency_state):
    """Map urgency to 4-tier system: overdue/critical/soon/upcoming/open."""
    if urgency_state == "open":
        return "open"
    if urgency_state == "overdue" or (time_remaining_seconds is not None and time_remaining_seconds <= 0):
        return "overdue"
    if time_remaining_seconds is not None:
        if time_remaining_seconds < 1800:   # < 30 min
            return "critical"
        if time_remaining_seconds < 21600:  # < 6 h
            return "soon"
        return "upcoming"
    return "open"


def _compute_urgency(thought, now, config):
    """Compute urgency metadata for a single reminder/todo thought."""
    text = thought.get("text", "")
    created_at = thought.get("created_at", "")
    try:
        created_dt = datetime.strptime(created_at, "%Y-%m-%dT%H:%M:%S")
    except (ValueError, TypeError):
        created_dt = now - timedelta(hours=1)

    # Parse relative/fuzzy phrases against creation-time context so due anchors
    # stay stable and do not roll forward on each poll.
    parsed = parse_time_signal(text, now=created_dt, config=config)
    anchor = parsed.get("anchor")
    zone = parsed.get("zone")

    urgency_ratio = 0.0
    urgency_state = "calm"
    time_remaining_seconds = None
    deadline_label = _compute_deadline_label(zone, anchor, now)

    if anchor:
        anchor_dt = anchor if isinstance(anchor, datetime) else datetime.fromisoformat(str(anchor))

        total_window = (anchor_dt - created_dt).total_seconds()
        elapsed = (now - created_dt).total_seconds()
        remaining = (anchor_dt - now).total_seconds()
        time_remaining_seconds = remaining

        if total_window > 0:
            urgency_ratio = min(1.0, max(0.0, elapsed / total_window))

        if remaining <= 0:
            urgency_state = "overdue"
            urgency_ratio = 1.0
        elif urgency_ratio >= 0.95:
            urgency_state = "critical"
        elif urgency_ratio >= 0.75:
            urgency_state = "hot"
        elif urgency_ratio >= 0.50:
            urgency_state = "warming"
        else:
            urgency_state = "calm"
    else:
        urgency_state = "open"
        urgency_ratio = 0.0

    return {
        "zone": zone,
        "deadline_label": deadline_label,
        "urgency_ratio": round(urgency_ratio, 3),
        "urgency_state": urgency_state,
        "time_remaining_seconds": int(time_remaining_seconds) if time_remaining_seconds is not None else None,
        "anchor_iso": anchor.isoformat() if anchor else None,
    }


def enrich_thought_alarm_fields(thoughts):
    """Attach alarm metadata used by reminder/todo widgets."""
    if not thoughts:
        return thoughts

    alarm_tags = {"reminder", "todo", "private_reminder", "private_todo"}
    counts = _get_pending_alarm_counts([t["id"] for t in thoughts])
    cfg = get_alarm_config()
    now = datetime.now()

    for thought in thoughts:
        thought["pending_alarm_count"] = int(counts.get(thought["id"], 0))
        thought["alarm_zone"] = None
        thought["alarm_anchor"] = None
        thought["alarm_raw_match"] = None
        thought["deadline_label"] = None

        if alarm_tags.intersection(set(thought.get("tags", []))):
            parsed = parse_time_signal(thought.get("text", ""), now=now, config=cfg)
            thought["alarm_zone"] = parsed.get("zone")
            thought["alarm_raw_match"] = parsed.get("raw_match")
            anchor = parsed.get("anchor")
            thought["alarm_anchor"] = anchor.isoformat() if anchor else None
            thought["deadline_label"] = _compute_deadline_label(
                parsed.get("zone"), anchor, now
            )

    return thoughts


def _maybe_cancel_alarms(conn, thought_id):
    """Best-effort cleanup for optional alarms table.

    Headlog can run without alarms; if an `alarms` table exists, remove rows
    for the deleted thought to avoid orphaned scheduled entries.
    """
    try:
        exists = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='alarms'"
        ).fetchone()
        if not exists:
            return

        cols = [
            r[1] for r in conn.execute("PRAGMA table_info(alarms)").fetchall()
        ]
        if "thought_id" in cols:
            conn.execute("DELETE FROM alarms WHERE thought_id = ?", (thought_id,))
        elif "thoughtId" in cols:
            conn.execute("DELETE FROM alarms WHERE thoughtId = ?", (thought_id,))
    except Exception:
        return


def delete_thought(thought_id):
    conn = get_db()
    try:
        row = conn.execute("SELECT * FROM thoughts WHERE id = ?", (thought_id,)).fetchone()
        if not row:
            return None
        thought = _row_to_dict(row)
        _maybe_cancel_alarms(conn, thought_id)
        conn.execute("DELETE FROM thoughts WHERE id = ?", (thought_id,))
        conn.commit()
        return thought
    finally:
        conn.close()


def edit_thought(thought_id, new_text, new_priority_override=None):
    """Edit a thought's text and recompute tags + priority.

    new_priority_override: if provided (from the PUT body), overrides any
    inline #p0 in the text. Pass the string 'none' to explicitly clear priority.
    """
    cleaned = (new_text or "").strip()
    if not cleaned:
        return None, {"error": "text is required"}, 400

    conn = get_db()
    try:
        row = conn.execute("SELECT * FROM thoughts WHERE id = ?", (thought_id,)).fetchone()
        if not row:
            return None, {"error": "Thought not found"}, 404

        thought = _row_to_dict(row)
        old_text = thought["text"]
        old_tags = thought["tags"]
        old_priority = thought.get("priority")

        cleaned, extracted_priority = extract_priority(cleaned)

        if new_priority_override is not None:
            if str(new_priority_override).lower() == 'none':
                priority = None
            elif str(new_priority_override).lower() in VALID_PRIORITIES:
                priority = str(new_priority_override).lower()
            else:
                priority = old_priority
        elif extracted_priority:
            priority = extracted_priority
        else:
            priority = old_priority

        if cleaned == (old_text or "").strip() and priority == old_priority:
            return thought, {"success": True, "changed": False}, 200

        old_auto_tags = auto_tag(old_text)
        manual_tags = [t for t in old_tags if t not in old_auto_tags]

        detected = auto_tag(cleaned)
        merged_tags = merge_tags(manual_tags, detected)

        if merged_tags == ["random"]:
            ai_tags = quick_ai_classify(cleaned)
            if ai_tags:
                merged_tags = ai_tags
                detected = ai_tags

        merged_tags = strip_priority_from_tags(merged_tags)

        now_iso = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        new_word_count = len(cleaned.split())
        is_private = 1 if PRIVATE_TAGS & set(merged_tags) else 0

        conn.execute(
            "INSERT INTO thought_edits (thought_id, old_text, new_text, old_tags, new_tags, edited_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                thought_id,
                old_text,
                cleaned,
                json.dumps(old_tags),
                json.dumps(merged_tags),
                now_iso,
            ),
        )

        conn.execute(
            "UPDATE thoughts SET text = ?, tags = ?, word_count = ?, is_private = ?, "
            "edited_at = ?, priority = ? WHERE id = ?",
            (cleaned, json.dumps(merged_tags), new_word_count, is_private, now_iso,
             priority, thought_id),
        )
        conn.commit()

        updated_row = conn.execute("SELECT * FROM thoughts WHERE id = ?", (thought_id,)).fetchone()
        updated = _row_to_dict(updated_row) if updated_row else thought
    finally:
        conn.close()

    try:
        update_markdown_journal(thought, cleaned, merged_tags, priority=priority)
    except Exception as je:
        print(f"Journal update failed: {je}")

    try:
        maybe_enrich(updated)
    except Exception:
        pass

    # Re-predict emoji if text changed substantially (>30% word diff)
    try:
        old_words = set(old_text.lower().split())
        new_words = set(cleaned.lower().split())
        if old_words and new_words:
            diff_ratio = len(old_words.symmetric_difference(new_words)) / max(len(old_words), len(new_words))
            if diff_ratio > 0.3:
                conn2 = get_db()
                try:
                    conn2.execute("UPDATE thoughts SET emoji = NULL WHERE id = ?", (thought_id,))
                    conn2.commit()
                finally:
                    conn2.close()
                maybe_predict_emoji(updated)
    except Exception:
        pass

    return updated, {
        "success": True,
        "changed": True,
        "tags": merged_tags,
        "word_count": new_word_count,
        "edited_at": now_iso,
        "auto_tags": [t for t in detected if t != "random"],
        "manual_tags_preserved": manual_tags,
    }, 200


def get_thoughts(limit=50, offset=0, tag=None, date=None, status=None):
    clauses, params = [], []

    if tag:
        clauses.append("tags LIKE ?")
        params.append(f'%"{tag}"%')
    if date:
        clauses.append("date_key = ?")
        params.append(date)
    if status:
        if isinstance(status, list):
            placeholders = ",".join("?" for _ in status)
            clauses.append(f"status IN ({placeholders})")
            params.extend(status)
        else:
            clauses.append("status = ?")
            params.append(status)

    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = f"SELECT * FROM thoughts {where} ORDER BY created_at DESC LIMIT ? OFFSET ?"
    params += [limit, offset]

    conn = get_db()
    try:
        rows = conn.execute(sql, params).fetchall()
        thoughts = [_row_to_dict(r) for r in rows]
    finally:
        conn.close()
    return enrich_thought_alarm_fields(thoughts)


def search_thoughts(query, limit=50):
    conn = get_db()
    try:
        rows = conn.execute(
            """SELECT t.* FROM thoughts t
               WHERE t.id IN (SELECT rowid FROM thoughts_fts WHERE thoughts_fts MATCH ?)
               ORDER BY t.created_at DESC LIMIT ?""",
            (query, limit),
        ).fetchall()
        thoughts = [_row_to_dict(r) for r in rows]
    finally:
        conn.close()
    return enrich_thought_alarm_fields(thoughts)


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

def write_to_journal(text, tags_list, created_at, priority=None):
    dt = datetime.strptime(created_at, "%Y-%m-%dT%H:%M:%S")
    year, month, day = dt.strftime("%Y"), dt.strftime("%m"), dt.strftime("%d")
    time_str = dt.strftime("%H:%M:%S")
    full_date = f"{dt.strftime('%A')}, {dt.strftime('%B')} {dt.day}, {dt.year}"

    dir_path = JOURNAL_DIR / year / month
    dir_path.mkdir(parents=True, exist_ok=True)

    file_path = dir_path / f"{year}-{month}-{day}.md"
    tags_str = ", ".join(f"#{t}" for t in tags_list) if tags_list else "#random"
    priority_str = f"[{priority.upper()}] " if priority else ""
    entry = f"\n### {time_str}  {priority_str}{tags_str}\n{text}\n\n---\n"

    if file_path.exists():
        with open(file_path, "a", encoding="utf-8") as f:
            f.write(entry)
    else:
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(f"# Thoughts — {full_date}\n")
            f.write(entry)


def update_markdown_journal(thought, new_text, new_tags, priority=None):
    """Replace a thought's text and tags in the daily journal file.

    Safety: If the entry isn't found, do nothing (never corrupt the file).
    """
    try:
        created_at = thought.get("created_at")
        if not created_at:
            return

        old_text = (thought.get("text") or "").strip()

        dt = datetime.strptime(created_at, "%Y-%m-%dT%H:%M:%S")
        year, month, day = dt.strftime("%Y"), dt.strftime("%m"), dt.strftime("%d")
        time_str = dt.strftime("%H:%M:%S")

        file_path = JOURNAL_DIR / year / month / f"{year}-{month}-{day}.md"
        if not file_path.exists():
            return

        content = file_path.read_text(encoding="utf-8")

        cleaned = (new_text or "").rstrip()
        tags_str = ", ".join(f"#{t}" for t in (new_tags or ["random"]))
        priority_str = f"[{priority.upper()}] " if priority else ""
        replacement = f"\n### {time_str}  {priority_str}{tags_str}  *(edited)*\n{cleaned}\n\n---\n"

        pattern = re.compile(
            rf"\n### {re.escape(time_str)}[ \t]+[^\n]*\n.*?\n---\n",
            re.DOTALL,
        )
        matches = list(pattern.finditer(content))
        if not matches:
            return

        chosen = None
        if old_text:
            for m in matches:
                block = content[m.start():m.end()]
                if old_text in block:
                    chosen = m
                    break

        # Fall back only if unambiguous
        if not chosen:
            if len(matches) == 1:
                chosen = matches[0]
            else:
                return

        updated = content[:chosen.start()] + replacement + content[chosen.end():]
        file_path.write_text(updated, encoding="utf-8")
    except Exception:
        return


def remove_from_journal(created_at, text):
    try:
        dt = datetime.strptime(created_at, "%Y-%m-%dT%H:%M:%S")
        year, month, day = dt.strftime("%Y"), dt.strftime("%m"), dt.strftime("%d")
        time_str = dt.strftime("%H:%M:%S")

        file_path = JOURNAL_DIR / year / month / f"{year}-{month}-{day}.md"
        if not file_path.exists():
            return

        content = file_path.read_text(encoding="utf-8")
        marker = f"\n### {time_str}  "
        start = content.find(marker)
        if start == -1:
            return

        end_marker = "\n---\n"
        end = content.find(end_marker, start)
        if end == -1:
            return

        if text not in content[start:end + len(end_marker)]:
            return

        updated = content[:start] + content[end + len(end_marker):]

        stripped = updated.strip()
        if stripped.startswith("# Thoughts") and "### " not in stripped:
            file_path.unlink()
        else:
            file_path.write_text(updated, encoding="utf-8")
    except Exception as e:
        print(f"Journal removal error: {e}")


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
        write_to_journal(d["text"], d["tags"], d["created_at"], priority=d.get("priority"))

    return len(days)


# ── Routines ─────────────────────────────────────────────────────

_DAY_NAMES = {
    'monday': 0, 'mon': 0,
    'tuesday': 1, 'tue': 1, 'tues': 1,
    'wednesday': 2, 'wed': 2,
    'thursday': 3, 'thu': 3, 'thur': 3, 'thurs': 3,
    'friday': 4, 'fri': 4,
    'saturday': 5, 'sat': 5,
    'sunday': 6, 'sun': 6,
}
_DAY_ABBREVS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']

_DAY_NAME_RE = re.compile(
    r'\b(' + '|'.join(re.escape(d) for d in _DAY_NAMES) + r')\b',
    re.IGNORECASE,
)


def _clean_routine_title(text):
    """Strip schedule-related phrases from text to get clean routine title."""
    cleaned = text.strip()
    day_alts = '|'.join(re.escape(d) for d in _DAY_NAMES)
    cleaned = re.sub(
        r'\s*\b(?:every|on)\s+(?:(?:' + day_alts + r')[\s,]*(?:and\s+)?)+',
        '', cleaned, flags=re.IGNORECASE,
    )
    cleaned = re.sub(
        r'\s*\b(?:every\s+(?:day|other\s+day|weekday|weekend|two\s+weeks|2\s+weeks|month|morning|evening|night)'
        r'|daily|weekdays?|weekends?|biweekly|fortnightly|monthly)\b',
        '', cleaned, flags=re.IGNORECASE,
    )
    cleaned = re.sub(
        r'\s*\b(?:on\s+the\s+)?\d{1,2}(?:st|nd|rd|th)\s*(?:of\s+every\s+month)?\b',
        '', cleaned, flags=re.IGNORECASE,
    )
    cleaned = re.sub(r'\s{2,}', ' ', cleaned).strip(' ,.-')
    if cleaned and cleaned[0].islower():
        cleaned = cleaned[0].upper() + cleaned[1:]
    return cleaned if cleaned else text.strip()


def parse_routine_schedule(text):
    """Extract recurrence pattern from natural language text."""
    lower = text.lower().strip()
    today = datetime.now()

    day_matches = _DAY_NAME_RE.findall(lower)
    if day_matches:
        days = sorted(set(_DAY_NAMES[d.lower()] for d in day_matches))
        has_ctx = any(w in lower for w in ('every', 'on '))
        if has_ctx or len(days) > 1:
            return {
                'title': _clean_routine_title(text),
                'schedule_type': 'specific_days',
                'schedule_data': {'days': days},
            }

    if re.search(r'\bdaily\b|\bevery\s*day\b|\beveryday\b', lower):
        return {'title': _clean_routine_title(text), 'schedule_type': 'daily', 'schedule_data': {}}

    if re.search(r'\bweekdays?\b|\bevery\s+weekday\b', lower):
        return {'title': _clean_routine_title(text), 'schedule_type': 'weekdays', 'schedule_data': {}}

    if re.search(r'\bweekends?\b|\bevery\s+weekend\b', lower):
        return {'title': _clean_routine_title(text), 'schedule_type': 'weekends', 'schedule_data': {}}

    if re.search(r'\bbiweekly\b|\bevery\s+(?:two|2)\s+weeks?\b|\bfortnightly\b', lower):
        return {
            'title': _clean_routine_title(text),
            'schedule_type': 'interval',
            'schedule_data': {'every_n_days': 14, 'anchor_date': today.strftime('%Y-%m-%d')},
        }

    if re.search(r'\bevery\s+other\s+day\b', lower):
        return {
            'title': _clean_routine_title(text),
            'schedule_type': 'interval',
            'schedule_data': {'every_n_days': 2, 'anchor_date': today.strftime('%Y-%m-%d')},
        }

    if re.search(r'\bmonthly\b|\bevery\s+month\b', lower):
        return {
            'title': _clean_routine_title(text),
            'schedule_type': 'monthly',
            'schedule_data': {'day_of_month': today.day},
        }

    ordinal = re.search(r'\b(?:on\s+the\s+)?(\d{1,2})(?:st|nd|rd|th)\s*(?:of\s+every\s+month)?\b', lower)
    if ordinal:
        dom = int(ordinal.group(1))
        if 1 <= dom <= 31:
            return {
                'title': _clean_routine_title(text),
                'schedule_type': 'monthly',
                'schedule_data': {'day_of_month': dom},
            }

    return {'title': text.strip(), 'schedule_type': 'daily', 'schedule_data': {}}


def _is_scheduled_on_date(schedule_type, schedule_data, check_date):
    """Check if a routine is scheduled for a given date."""
    wd = check_date.weekday()
    if schedule_type == 'daily':
        return True
    if schedule_type == 'weekdays':
        return wd < 5
    if schedule_type == 'weekends':
        return wd >= 5
    if schedule_type == 'specific_days':
        return wd in schedule_data.get('days', [])
    if schedule_type == 'interval':
        anchor = schedule_data.get('anchor_date')
        every_n = schedule_data.get('every_n_days', 1)
        if not anchor:
            return True
        anchor_date = datetime.strptime(anchor, '%Y-%m-%d').date()
        diff = (check_date - anchor_date).days
        return diff >= 0 and diff % every_n == 0
    if schedule_type == 'monthly':
        dom = schedule_data.get('day_of_month', 1)
        last_day = calendar.monthrange(check_date.year, check_date.month)[1]
        return check_date.day == min(dom, last_day)
    return False


def _get_schedule_label(schedule_type, schedule_data):
    """Human-readable schedule label."""
    if schedule_type == 'daily':
        return 'Daily'
    if schedule_type == 'weekdays':
        return 'Weekdays'
    if schedule_type == 'weekends':
        return 'Weekends'
    if schedule_type == 'specific_days':
        days = schedule_data.get('days', [])
        return ', '.join(_DAY_ABBREVS[d] for d in sorted(days))
    if schedule_type == 'interval':
        n = schedule_data.get('every_n_days', 1)
        if n == 14:
            return 'Every 2 weeks'
        if n == 2:
            return 'Every other day'
        return f'Every {n} days'
    if schedule_type == 'monthly':
        dom = schedule_data.get('day_of_month', 1)
        suffix = {1: 'st', 2: 'nd', 3: 'rd'}.get(dom if dom < 20 else dom % 10, 'th')
        return f'Monthly ({dom}{suffix})'
    return schedule_type


def _get_last_n_scheduled_dates(schedule_type, schedule_data, n=7, ref_date=None):
    """Get the last N scheduled dates (including ref_date), newest first."""
    if ref_date is None:
        ref_date = datetime.now().date()
    dates = []
    d = ref_date
    limit = ref_date - timedelta(days=365)
    while len(dates) < n and d >= limit:
        if _is_scheduled_on_date(schedule_type, schedule_data, d):
            dates.append(d)
        d -= timedelta(days=1)
    return dates


def _compute_consistency(routine_id, schedule_type, schedule_data, conn, ref_date=None):
    """Compute consistency dots and needs_attention flag."""
    if ref_date is None:
        ref_date = datetime.now().date()

    scheduled_dates = _get_last_n_scheduled_dates(schedule_type, schedule_data, 7, ref_date)

    if not scheduled_dates:
        return [False] * 7, False, 0

    date_strs = [d.strftime('%Y-%m-%d') for d in scheduled_dates]
    placeholders = ','.join('?' for _ in date_strs)
    rows = conn.execute(
        f"SELECT completed_date FROM routine_completions "
        f"WHERE routine_id = ? AND completed_date IN ({placeholders})",
        [routine_id] + date_strs,
    ).fetchall()
    completed_set = {r['completed_date'] for r in rows}

    dots = [d.strftime('%Y-%m-%d') in completed_set for d in scheduled_dates]

    # needs_attention: 2+ consecutive misses before today
    past_dates = _get_last_n_scheduled_dates(schedule_type, schedule_data, 3, ref_date - timedelta(days=1))
    missed_consecutive = 0
    for d in past_dates:
        ds = d.strftime('%Y-%m-%d')
        check = conn.execute(
            "SELECT 1 FROM routine_completions WHERE routine_id = ? AND completed_date = ?",
            (routine_id, ds),
        ).fetchone()
        if check:
            break
        missed_consecutive += 1

    filled = sum(dots)
    pct = round(filled / len(dots) * 100) if dots else 0

    return dots, missed_consecutive >= 2, pct


def save_routine(thought_id, title, schedule_type, schedule_data):
    """Create a routine, or return existing if duplicate title."""
    conn = get_db()
    try:
        existing = conn.execute(
            "SELECT id FROM routines WHERE LOWER(title) = LOWER(?) AND status = 'active'",
            (title,),
        ).fetchone()
        if existing:
            return existing['id'], True

        now_iso = datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
        schedule_json = json.dumps(schedule_data)
        cur = conn.execute(
            "INSERT INTO routines (thought_id, title, schedule_type, schedule_data, status, created_at) "
            "VALUES (?, ?, ?, ?, 'active', ?)",
            (thought_id, title, schedule_type, schedule_json, now_iso),
        )
        conn.commit()
        return cur.lastrowid, False
    finally:
        conn.close()


# ── Config ────────────────────────────────────────────────────────

def _default_alarm_config():
    return {
        "sounds_enabled": bool(DEFAULT_ALARM_CONFIG.get("sounds_enabled", True)),
        "quiet_hours": dict(DEFAULT_ALARM_CONFIG.get("quiet_hours", {"start": "22:00", "end": "08:00"})),
        "fuzzy_mappings": dict(DEFAULT_ALARM_CONFIG.get("fuzzy_mappings", {})),
        "open_todo_days": list(DEFAULT_ALARM_CONFIG.get("open_todo_days", [2, 5, 10, 21])),
        "day_bound_times": list(DEFAULT_ALARM_CONFIG.get("day_bound_times", ["09:00", "14:00", "18:00"])),
    }


def _default_config():
    return {
        "ai_provider": "ollama",
        "ai_model": "llama3.2:3b",
        "api_key": "",
        "alarms": _default_alarm_config(),
    }


def _normalize_alarm_config(raw_alarm_cfg):
    merged = _default_alarm_config()
    if not isinstance(raw_alarm_cfg, dict):
        return merged

    if "sounds_enabled" in raw_alarm_cfg:
        merged["sounds_enabled"] = bool(raw_alarm_cfg["sounds_enabled"])

    quiet_hours = raw_alarm_cfg.get("quiet_hours")
    if isinstance(quiet_hours, dict):
        if "start" in quiet_hours:
            merged["quiet_hours"]["start"] = str(quiet_hours["start"])
        if "end" in quiet_hours:
            merged["quiet_hours"]["end"] = str(quiet_hours["end"])

    # Backward compatibility with flat keys.
    if "quiet_hours_start" in raw_alarm_cfg:
        merged["quiet_hours"]["start"] = str(raw_alarm_cfg["quiet_hours_start"])
    if "quiet_hours_end" in raw_alarm_cfg:
        merged["quiet_hours"]["end"] = str(raw_alarm_cfg["quiet_hours_end"])

    fuzzy = raw_alarm_cfg.get("fuzzy_mappings")
    if isinstance(fuzzy, dict):
        for key in ("morning", "noon", "afternoon", "evening", "night"):
            if key in fuzzy:
                merged["fuzzy_mappings"][key] = str(fuzzy[key])

    open_days = raw_alarm_cfg.get("open_todo_days")
    if isinstance(open_days, list) and len(open_days) >= 4:
        merged["open_todo_days"] = [int(v) for v in open_days[:4]]

    day_times = raw_alarm_cfg.get("day_bound_times")
    if isinstance(day_times, list) and len(day_times) >= 3:
        merged["day_bound_times"] = [str(v) for v in day_times[:3]]

    return merged


def load_config():
    base = _default_config()
    loaded = {}
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH, encoding="utf-8") as f:
                loaded = json.load(f)
        except Exception:
            pass

    if not isinstance(loaded, dict):
        loaded = {}

    merged = {
        "ai_provider": loaded.get("ai_provider", base["ai_provider"]),
        "ai_model": loaded.get("ai_model", base["ai_model"]),
        "api_key": loaded.get("api_key", base["api_key"]),
        "alarms": _normalize_alarm_config(loaded.get("alarms", {})),
    }
    return merged


def save_config(config):
    base = load_config()
    payload = dict(base)
    if isinstance(config, dict):
        payload.update({k: v for k, v in config.items() if k != "alarms"})
        payload["alarms"] = _normalize_alarm_config(config.get("alarms", payload.get("alarms", {})))

    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)


def get_alarm_config():
    return load_config().get("alarms", _default_alarm_config())


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

def _call_ai_classify(prompt, config, timeout=30, max_tokens=50):
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
                "generationConfig": {"temperature": 0.1, "maxOutputTokens": max_tokens},
            }).encode()
            req = urllib.request.Request(
                url, data=data, headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                result = json.loads(resp.read())
                return result["candidates"][0]["content"]["parts"][0]["text"]
        except Exception:
            return None

    try:
        data = json.dumps({
            "model": model, "prompt": prompt, "stream": False,
            "options": {"temperature": 0.1, "num_predict": max_tokens},
        }).encode()
        req = urllib.request.Request(
            "http://localhost:11434/api/generate",
            data=data, headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
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
        tags_str = ", ".join(f"#{t}" for t in (new_tags or ["random"]))

        # Preserve existing priority prefix and "*(edited)*" marker if present.
        pattern = re.compile(rf"(### {re.escape(time_str)}  )([^\n]+)")

        def _repl(m):
            rest = m.group(2)
            suffix = "  *(edited)*" if re.search(r"\s+\*\(edited\)\*\s*$", rest) else ""
            priority_match = re.match(r'(\[P[0-2]\] )', rest)
            priority_prefix = priority_match.group(1) if priority_match else ""
            return f"{m.group(1)}{priority_prefix}{tags_str}{suffix}"

        updated = pattern.sub(_repl, content, count=1)

        if updated != content:
            file_path.write_text(updated, encoding="utf-8")
    except Exception:
        pass


def ai_enrich_tags(thought_id, text, existing_tags, date_key, created_at, expected_edited_at=None):
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
            "- Do NOT suggest: private_todo, private_reminder, routine, random, p0, p1, p2\n"
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
        new_ai_tags = [t for t in new_ai_tags if t != "routine"]
        if not _allow_ai_action_tags(text):
            new_ai_tags = [t for t in new_ai_tags if t not in {"todo", "reminder"}]
        if not new_ai_tags:
            return

        # Guard against stale enrichment: if the thought was edited after this
        # enrichment started, discard the AI result instead of overwriting intent.
        try:
            conn_guard = get_db()
            try:
                cur = conn_guard.execute(
                    "SELECT edited_at FROM thoughts WHERE id = ?",
                    (thought_id,),
                ).fetchone()
            finally:
                conn_guard.close()
            if not cur:
                return
            if cur["edited_at"] != expected_edited_at:
                return
        except Exception:
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
              thought["date_key"], thought["created_at"], thought.get("edited_at")),
        daemon=True,
    ).start()


def build_emoji_prompt(text):
    return (
        'You are an emoji classifier. Given a task, reminder, or routine, '
        'respond with exactly ONE emoji that best represents it.\n\n'
        'Rules:\n'
        '- Respond with ONLY the emoji character, nothing else\n'
        '- No text, no explanation, no punctuation, no notes\n'
        '- Pick the most specific and recognizable emoji for the activity\n'
        '- Examples:\n'
        '  "go to gym at 7AM" \u2192 \U0001f4aa\n'
        '  "take protein shake" \u2192 \U0001f964\n'
        '  "buy groceries" \u2192 \U0001f6d2\n'
        '  "call mom" \u2192 \U0001f4de\n'
        '  "read 20 pages of book" \u2192 \U0001f4d6\n'
        '  "deploy the API endpoint" \u2192 \U0001f680\n'
        '  "pay electricity bill" \u2192 \U0001f4a1\n'
        '  "take creatine every morning" \u2192 \U0001f48a\n'
        '  "water the plants" \u2192 \U0001f331\n'
        '  "team standup at 10" \u2192 \U0001f465\n'
        '  "dentist appointment at 3pm" \u2192 \U0001f9b7\n'
        '  "submit tax documents" \u2192 \U0001f4c4\n'
        '  "pick up laundry" \u2192 \U0001f454\n'
        '  "meditate for 10 minutes" \u2192 \U0001f9d8\n'
        '  "buy milk" \u2192 \U0001f95b\n\n'
        f'Task: "{text}"\nEmoji:'
    )


_EMOJI_RE = re.compile(
    "["
    "\U0001F300-\U0001F9FF"
    "\U00002702-\U000027B0"
    "\U0000FE00-\U0000FE0F"
    "\U0000200D"
    "\U000024C2-\U0001F251"
    "\U0001FA00-\U0001FA6F"
    "\U0001FA70-\U0001FAFF"
    "]+",
    flags=re.UNICODE,
)


def extract_single_emoji(text):
    """Extract the first emoji from an AI response. Returns None if not found."""
    if not text:
        return None
    text = text.strip().strip('"').strip("'").strip('`').strip()
    match = _EMOJI_RE.search(text)
    if match:
        emoji = match.group(0)
        if len(emoji) <= 8:
            return emoji
    return None


def ai_predict_emoji(thought_id, text, tags):
    """Background task: predict a single emoji for a todo/reminder/routine thought."""
    actionable_tags = {'todo', 'reminder', 'routine', 'private_todo', 'private_reminder'}
    thought_tags = set(tags) if isinstance(tags, list) else set(json.loads(tags or '[]'))
    if not thought_tags.intersection(actionable_tags):
        return

    # Skip prediction if the text already begins with an emoji.
    if text and _EMOJI_RE.match(text.strip()):
        return

    if not _enrich_semaphore.acquire(blocking=False):
        return

    try:
        config = load_config()
        provider = config.get('ai_provider', 'ollama')
        if provider == 'none':
            return
        if provider == 'gemini' and not config.get('api_key'):
            return

        prompt = build_emoji_prompt(text)

        if provider == 'gemini':
            api_key = config.get('api_key', '')
            model = config.get('ai_model', 'gemini-2.0-flash-lite')
            raw = None
            try:
                url = (f"https://generativelanguage.googleapis.com/v1beta/"
                       f"models/{model}:generateContent?key={api_key}")
                data = json.dumps({
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {"temperature": 0.3, "maxOutputTokens": 10},
                }).encode()
                req = urllib.request.Request(
                    url, data=data, headers={"Content-Type": "application/json"},
                )
                with urllib.request.urlopen(req, timeout=15) as resp:
                    result = json.loads(resp.read())
                    raw = result["candidates"][0]["content"]["parts"][0]["text"]
            except Exception:
                return
        else:
            model = config.get('ai_model', 'llama3.2:3b')
            raw = None
            try:
                data = json.dumps({
                    "model": model, "prompt": prompt, "stream": False,
                    "options": {"temperature": 0.3, "num_predict": 10},
                }).encode()
                req = urllib.request.Request(
                    "http://localhost:11434/api/generate",
                    data=data, headers={"Content-Type": "application/json"},
                )
                with urllib.request.urlopen(req, timeout=15) as resp:
                    raw = json.loads(resp.read()).get("response")
            except urllib.error.URLError:
                return
            except Exception:
                return

        if not raw:
            return

        emoji = extract_single_emoji(raw.strip())
        if not emoji:
            return

        conn = sqlite3.connect(str(DB_PATH))
        try:
            conn.execute(
                "UPDATE thoughts SET emoji = ? WHERE id = ? AND emoji IS NULL",
                (emoji, thought_id),
            )
            conn.commit()
        finally:
            conn.close()

        print(f"[emoji-predict] thought {thought_id}: {emoji}")

    except Exception as e:
        print(f"[emoji-predict] Error for thought {thought_id}: {e}")
    finally:
        _enrich_semaphore.release()


def maybe_predict_emoji(thought):
    """Spawn emoji prediction in a background thread if conditions are met."""
    config = load_config()
    provider = config.get('ai_provider', 'ollama')
    if provider == 'none':
        return
    if provider == 'gemini' and not config.get('api_key'):
        return
    threading.Thread(
        target=ai_predict_emoji,
        args=(thought['id'], thought['text'], thought['tags']),
        daemon=True,
    ).start()


def quick_ai_classify(text):
    """Synchronous LLM fallback when keyword detection yields only 'random'.

    Uses a tight timeout so the save path stays responsive; returns None
    (caller keeps 'random') if the LLM is unavailable or too slow.
    """
    config = load_config()
    provider = config.get("ai_provider", "ollama")
    if provider == "none":
        return None
    if provider == "gemini" and not config.get("api_key"):
        return None

    prompt = (
        "Classify this personal note into 1-2 tags from this EXACT list only:\n\n"
        "routine, health, finance, idea, career, learning, tech, "
        "productivity, spiritual, reflection, gratitude, vent, lesson, "
        "decision, question, todo, reminder, people, selfhelp, travel\n\n"
        "Rules:\n"
        "- Return ONLY comma-separated tag names, nothing else\n"
        "- For action items, tasks, or imperative sentences → todo\n"
        "- For time-bound items with deadlines → add reminder\n"
        "- Do NOT suggest: private_todo, private_reminder, routine, p0, p1, p2\n"
        "- If genuinely uncategorizable → return: random\n\n"
        f'Note: "{text}"\n\nTags:'
    )

    raw = _call_ai_classify(prompt, config, timeout=8, max_tokens=30)
    if not raw:
        return None

    candidates = [t.strip().lower().rstrip(".") for t in raw.split(",")]
    valid = [t for t in candidates if t in VALID_ENRICHMENT_TAGS and t != "routine"]
    if not _allow_ai_action_tags(text):
        valid = [t for t in valid if t not in {"todo", "reminder"}]
    return valid or None


def expire_old_reminders():
    """Transition active reminders whose time anchor is >24h past to 'expired'.

    Only affects thoughts where ALL alarms have fired/dismissed/cancelled
    (i.e., no pending alarms remain).
    """
    cutoff = (datetime.now() - timedelta(hours=24)).isoformat()

    conn = get_db()
    try:
        rows = conn.execute("""
            SELECT t.id, t.tags, t.created_at
            FROM thoughts t
            WHERE t.status = 'active'
              AND (t.tags LIKE '%"reminder"%' OR t.tags LIKE '%"private_reminder"%')
              AND t.created_at < ?
              AND NOT EXISTS (
                  SELECT 1 FROM alarms a
                  WHERE a.thought_id = t.id AND a.status = 'pending'
              )
        """, (cutoff,)).fetchall()

        expired_ids = [row["id"] for row in rows]

        if expired_ids:
            placeholders = ",".join("?" for _ in expired_ids)
            conn.execute(
                f"UPDATE thoughts SET status = 'expired' WHERE id IN ({placeholders})",
                expired_ids,
            )
            conn.commit()
            print(f"Auto-expired {len(expired_ids)} old reminder(s)")

    except Exception as e:
        print(f"Auto-expire error: {e}")
    finally:
        conn.close()


# ── Alarm Scheduler ───────────────────────────────────────────────

class AlarmScheduler:
    def __init__(self, db_path):
        self.db_path = str(db_path)
        self._stop = threading.Event()
        self._wake = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def start(self):
        self._thread.start()

    def stop(self):
        self._stop.set()
        self._wake.set()

    def wake(self):
        self._wake.set()

    def _run(self):
        self._catch_up_missed()
        expire_old_reminders()
        _last_expire = datetime.now()

        while not self._stop.is_set():
            self._check_and_fire()

            if (datetime.now() - _last_expire) >= timedelta(hours=1):
                expire_old_reminders()
                _last_expire = datetime.now()

            self._wake.wait(timeout=30)
            self._wake.clear()

    def _check_and_fire(self):
        now = datetime.now()
        now_iso = now.isoformat()
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")

        try:
            due_rows = conn.execute(
                "SELECT a.*, t.tags, t.text AS thought_text, t.emoji AS thought_emoji "
                "FROM alarms a JOIN thoughts t ON a.thought_id = t.id "
                "WHERE a.status = 'pending' AND a.fire_at <= ? "
                "ORDER BY a.fire_at ASC",
                (now_iso,),
            ).fetchall()

            for alarm in due_rows:
                if alarm["zone"] != "pinned" and self._in_quiet_hours(now):
                    continue

                tags = json.loads(alarm["tags"]) if alarm["tags"] else []
                is_private = bool({"private_reminder", "private_todo"}.intersection(set(tags)))

                if is_private:
                    title = "🔒 Private reminder"
                    body = "Tap to view in Headlog"
                else:
                    thought_emoji = alarm["thought_emoji"] or ""
                    base_title = self._zone_title(alarm["zone"], alarm["sequence_index"])
                    title = f"{thought_emoji} {base_title}".strip() if thought_emoji else base_title
                    body = alarm["message"]

                tags_set = set(tags)
                if alarm["zone"] == "open_todo":
                    _notif_type = "todo"
                elif alarm["zone"] == "overdue_repeat":
                    _notif_type = "overdue"
                elif "reminder" in tags_set or "private_reminder" in tags_set:
                    _notif_type = "reminder"
                elif "todo" in tags_set or "private_todo" in tags_set:
                    _notif_type = "todo"
                else:
                    _notif_type = "alarm"

                fire_notification(title, body, alarm["tone"],
                                  thought_id=alarm["thought_id"], notif_type=_notif_type)

                conn.execute(
                    "UPDATE alarms SET status = 'fired' WHERE id = ?",
                    (alarm["id"],),
                )

                if alarm["zone"] == "open_todo" and int(alarm["sequence_index"]) == 4:
                    conn.execute(
                        "UPDATE thoughts SET status = 'stale' WHERE id = ?",
                        (alarm["thought_id"],),
                    )

            conn.commit()
            self._schedule_overdue_repeats(conn)
        except Exception as err:
            print(f"[AlarmScheduler] Error: {err}")
        finally:
            conn.close()

    def _schedule_overdue_repeats(self, db):
        """For every active, unmuted thought that had time-based alarms (all fired,
        none pending), schedule a repeat overdue alert 10 min from now."""
        now = datetime.now()
        now_iso = now.isoformat()

        try:
            # Thoughts that are active, unmuted, have reminder/todo tags,
            # have at least one fired non-open_todo alarm (meaning they had a real anchor),
            # and have no pending alarms right now.
            overdue = db.execute("""
                SELECT t.id, t.text, t.tags, t.is_private,
                       MAX(a_fired.fire_at) AS last_fired_at
                FROM thoughts t
                JOIN alarms a_fired ON a_fired.thought_id = t.id
                WHERE t.status = 'active'
                  AND t.is_muted = 0
                  AND (t.tags LIKE '%"todo"%' OR t.tags LIKE '%"reminder"%'
                       OR t.tags LIKE '%"private_todo"%' OR t.tags LIKE '%"private_reminder"%')
                  AND a_fired.status = 'fired'
                  AND a_fired.zone NOT IN ('open_todo', 'overdue_repeat')
                  AND NOT EXISTS (
                      SELECT 1 FROM alarms a_pend
                      WHERE a_pend.thought_id = t.id
                      AND a_pend.status = 'pending'
                  )
                GROUP BY t.id
                HAVING MAX(a_fired.fire_at) < ?
            """, (now_iso,)).fetchall()
        except Exception as err:
            print(f"[AlarmScheduler] overdue_repeat query failed: {err}")
            return

        if not overdue:
            return

        next_fire = (now + timedelta(minutes=10)).isoformat()

        for thought in overdue:
            text = thought["text"] or ""
            if thought["is_private"]:
                display_text = "🔒 Tap to view in Headlog"
            else:
                display_text = (text[:77] + "...") if len(text) > 80 else text

            try:
                last_fired = datetime.fromisoformat(thought["last_fired_at"])
                overdue_delta = now - last_fired
                hours = int(overdue_delta.total_seconds() // 3600)
                mins = int((overdue_delta.total_seconds() % 3600) // 60)
                if hours > 0:
                    overdue_label = f"overdue {hours}h {mins}m"
                else:
                    overdue_label = f"overdue {mins}m"
            except Exception:
                overdue_label = "overdue"

            message = f"⏰ Still pending ({overdue_label}): {display_text}"

            try:
                db.execute(
                    "INSERT INTO alarms (thought_id, zone, sequence_index, fire_at, status, tone, message, created_at) "
                    "VALUES (?, 'overdue_repeat', 0, ?, 'pending', 'firm', ?, ?)",
                    (thought["id"], next_fire, message, now_iso),
                )
            except Exception as err:
                print(f"[AlarmScheduler] overdue_repeat insert failed: {err}")

        try:
            db.commit()
        except Exception as err:
            print(f"[AlarmScheduler] overdue_repeat commit failed: {err}")

    def _catch_up_missed(self):
        now_iso = datetime.now().isoformat()
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row

        try:
            row = conn.execute(
                "SELECT COUNT(*) AS cnt FROM alarms WHERE status = 'pending' AND fire_at <= ?",
                (now_iso,),
            ).fetchone()
            count = int(row["cnt"]) if row else 0
            if count <= 0:
                return

            fire_notification(
                "☀️ Headlog",
                f"Missed while away: {count} reminder{'s' if count != 1 else ''}",
                "gentle",
            )
            conn.execute(
                "UPDATE alarms SET status = 'fired' WHERE status = 'pending' AND fire_at <= ?",
                (now_iso,),
            )
            conn.commit()
        except Exception as err:
            print(f"[AlarmScheduler] Catch-up error: {err}")
        finally:
            conn.close()

    def _zone_title(self, zone, seq):
        if zone == "pinned":
            return {
                1: "🔔 In 60 minutes",
                2: "🔔 In 15 minutes",
                3: "🔔 Starting now",
                4: "🔔 Tomorrow",
            }.get(int(seq), "🔔 Reminder")
        if zone == "day_bound":
            return {
                1: "📋 Halfway there",
                2: "📋 Due tomorrow",
                3: "📋 Due today",
                4: "📋 Still due today",
                5: "📋 Deadline tonight",
            }.get(int(seq), "📋 Deadline")
        if zone == "soft":
            return {
                1: "☀️ On your plate",
                2: "☀️ Still on your plate",
                3: "☀️ Time to act",
            }.get(int(seq), "☀️ Reminder")
        if zone == "open_todo":
            return {
                1: "💭 Open todo",
                2: "💭 5 days open",
                3: "💭 10 days",
                4: "💭 3 weeks — act or drop?",
            }.get(int(seq), "💭 Todo")
        return "🔔 Reminder"

    def _in_quiet_hours(self, now):
        try:
            qh = get_alarm_config().get("quiet_hours", {})
            start = qh.get("start", "22:00")
            end = qh.get("end", "08:00")

            sh, sm = [int(x) for x in str(start).split(":")]
            eh, em = [int(x) for x in str(end).split(":")]
            now_mins = now.hour * 60 + now.minute
            start_mins = sh * 60 + sm
            end_mins = eh * 60 + em

            if start_mins > end_mins:
                return now_mins >= start_mins or now_mins < end_mins
            return start_mins <= now_mins < end_mins
        except Exception:
            return False


scheduler = None


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

        if path.startswith("/assets/sfx/"):
            filename = os.path.basename(path.split("/assets/sfx/")[-1])
            filepath = SFX_DIR / filename
            if filepath.exists() and filename.endswith(".mp3"):
                try:
                    data = filepath.read_bytes()
                    self.send_response(200)
                    self.send_header("Content-Type", mimetypes.guess_type(str(filepath))[0] or "audio/mpeg")
                    self.send_header("Content-Length", str(len(data)))
                    self.send_header("Cache-Control", "max-age=86400")
                    self.end_headers()
                    self.wfile.write(data)
                    return
                except Exception as err:
                    return self._json_response({"error": str(err)}, 500)

            self.send_response(404)
            self.end_headers()
            return

        if path == "/api/thoughts":
            try:
                status_param = qs.get("status", [None])[0]
                status_filter = None
                if status_param:
                    status_filter = [s.strip() for s in status_param.split(",")]

                rows = get_thoughts(
                    limit=int(qs.get("limit", [50])[0]),
                    offset=int(qs.get("offset", [0])[0]),
                    tag=qs.get("tag", [None])[0],
                    date=qs.get("date", [None])[0],
                    status=status_filter,
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

        if path == "/api/alarms/active":
            try:
                five_min_ago = (datetime.now() - timedelta(minutes=5)).isoformat()
                conn = get_db()
                try:
                    rows = conn.execute(
                        "SELECT a.id, a.thought_id, a.zone, a.tone, a.message, a.fire_at, "
                        "t.text, t.tags, t.is_private "
                        "FROM alarms a JOIN thoughts t ON a.thought_id = t.id "
                        "WHERE a.status = 'fired' AND a.fire_at >= ? "
                        "ORDER BY a.fire_at DESC",
                        (five_min_ago,),
                    ).fetchall()
                    alarms = []
                    for row in rows:
                        tags = json.loads(row["tags"]) if row["tags"] else []
                        is_private = bool({"private_reminder", "private_todo"}.intersection(set(tags)))
                        alarms.append(
                            {
                                "id": row["id"],
                                "thought_id": row["thought_id"],
                                "zone": row["zone"],
                                "tone": row["tone"],
                                "message": row["message"],
                                "fire_at": row["fire_at"],
                                "text": "🔒 Private reminder" if is_private else row["text"],
                                "is_private": is_private,
                            }
                        )
                finally:
                    conn.close()
                return self._json_response({"alarms": alarms})
            except Exception as err:
                return self._json_response({"error": str(err)}, 500)

        if path == "/api/alarms/upcoming":
            thought_id_raw = qs.get("thought_id", [None])[0]
            if not thought_id_raw:
                return self._json_response({"error": "thought_id required"}, 400)
            try:
                thought_id = int(thought_id_raw)
                conn = get_db()
                try:
                    rows = conn.execute(
                        "SELECT id, thought_id, zone, sequence_index, fire_at, tone, status, message "
                        "FROM alarms WHERE thought_id = ? ORDER BY sequence_index ASC",
                        (thought_id,),
                    ).fetchall()
                    alarms = [dict(r) for r in rows]
                finally:
                    conn.close()
                return self._json_response({"alarms": alarms})
            except Exception as err:
                return self._json_response({"error": str(err)}, 500)

        if path == "/api/reminders/active":
            try:
                now = datetime.now()
                cfg = get_alarm_config()
                conn = get_db()
                try:
                    rows = conn.execute("""
                        SELECT t.*,
                               (SELECT COUNT(*) FROM alarms a
                                WHERE a.thought_id = t.id AND a.status = 'pending') as pending_alarms,
                               (SELECT MIN(a.fire_at) FROM alarms a
                                WHERE a.thought_id = t.id AND a.status = 'pending') as next_alarm_at
                        FROM thoughts t
                        WHERE t.status IN ('active', 'stale')
                          AND (
                            t.tags LIKE '%"reminder"%'
                            OR t.tags LIKE '%"private_reminder"%'
                            OR t.tags LIKE '%"todo"%'
                            OR t.tags LIKE '%"private_todo"%'
                          )
                        ORDER BY t.created_at DESC
                    """).fetchall()

                    items = []
                    seen_ids = set()
                    for row in rows:
                        thought = _row_to_dict(row)
                        if thought["id"] in seen_ids:
                            continue
                        seen_ids.add(thought["id"])
                        urgency = _compute_urgency(thought, now, cfg)

                        tags = thought.get("tags", [])
                        is_reminder = "reminder" in tags or "private_reminder" in tags
                        is_todo = "todo" in tags or "private_todo" in tags
                        item_type = "reminder" if (is_reminder and not is_todo) else "todo"

                        urgency_tier = _compute_urgency_tier(
                            urgency.get("time_remaining_seconds"),
                            urgency.get("urgency_state", "open"),
                        )
                        items.append({
                            "id": thought["id"],
                            "text": "🔒 Private" if thought.get("is_private") else thought["text"],
                            "is_private": bool(thought.get("is_private")),
                            "tags": [
                                t for t in tags
                                if t not in ("todo", "reminder", "private_todo", "private_reminder", "random")
                            ],
                            "priority": thought.get("priority"),
                            "created_at": thought["created_at"],
                            "item_type": item_type,
                            "pending_alarms": row["pending_alarms"],
                            "next_alarm_at": row["next_alarm_at"],
                            "urgency": urgency_tier,
                            **urgency,
                        })

                    state_order = {"overdue": 0, "critical": 1, "hot": 2, "warming": 3, "calm": 4, "open": 5}
                    items.sort(key=lambda r: (
                        state_order.get(r["urgency_state"], 6),
                        -r["urgency_ratio"],
                    ))

                    now_plus_4h = now + timedelta(hours=4)
                    today_end = now.replace(hour=23, minute=59, second=59, microsecond=999999)
                    week_end = now + timedelta(days=7)

                    for item in items:
                        anchor = item.get("anchor_iso")
                        anchor_dt = None
                        if anchor:
                            try:
                                anchor_dt = datetime.fromisoformat(anchor)
                            except (TypeError, ValueError):
                                anchor_dt = None
                        state = item["urgency_state"]
                        if state == "overdue":
                            item["bucket"] = "next_hours"
                        elif anchor_dt and anchor_dt <= now_plus_4h:
                            item["bucket"] = "next_hours"
                        elif anchor_dt and anchor_dt <= today_end:
                            item["bucket"] = "today"
                        elif anchor_dt and anchor_dt <= week_end:
                            item["bucket"] = "this_week"
                        elif anchor_dt:
                            item["bucket"] = "later"
                        else:
                            item["bucket"] = "open"

                    return self._json_response({
                        "items": items,
                        "count": len(items),
                    })
                finally:
                    conn.close()
            except Exception as e:
                return self._json_response({"error": str(e)}, 500)

        if path == "/api/reminders/briefing":
            try:
                now = datetime.now()
                today = now.strftime("%Y-%m-%d")
                cfg = get_alarm_config()
                conn = get_db()
                try:
                    active_tags_clause = """
                        (tags LIKE '%"reminder"%' OR tags LIKE '%"private_reminder"%'
                         OR tags LIKE '%"todo"%' OR tags LIKE '%"private_todo"%')
                    """

                    active_rows = conn.execute(f"""
                        SELECT * FROM thoughts
                        WHERE status IN ('active', 'stale') AND {active_tags_clause}
                        ORDER BY created_at DESC
                    """).fetchall()

                    active_items = []
                    seen_ids = set()
                    for row in active_rows:
                        thought = _row_to_dict(row)
                        if thought["id"] in seen_ids:
                            continue
                        seen_ids.add(thought["id"])
                        urgency = _compute_urgency(thought, now, cfg)
                        active_items.append({
                            "id": thought["id"],
                            "text": "🔒 Private" if thought.get("is_private") else thought["text"],
                            "is_private": bool(thought.get("is_private")),
                            **urgency,
                        })

                    total = len(active_items)

                    completed_today = conn.execute(
                        f"SELECT COUNT(*) as cnt FROM thoughts WHERE status = 'done' AND {active_tags_clause} AND date_key = ?",
                        (today,),
                    ).fetchone()["cnt"]

                    overdue = sum(
                        1 for item in active_items
                        if item.get("urgency_state") == "overdue"
                    )

                    next_deadline = None
                    with_anchor = [
                        item for item in active_items
                        if item.get("anchor_iso") and item.get("time_remaining_seconds") is not None
                    ]
                    upcoming = [
                        item for item in with_anchor
                        if item["time_remaining_seconds"] > 0
                    ]
                    if upcoming:
                        nearest = min(upcoming, key=lambda item: item["time_remaining_seconds"])
                        next_deadline = {
                            "fire_at": nearest["anchor_iso"],
                            "text": nearest["text"],
                            "is_private": nearest["is_private"],
                            "time_remaining_seconds": int(nearest["time_remaining_seconds"]),
                        }

                    yesterday = (now - timedelta(days=1)).strftime("%Y-%m-%d")
                    y_total = conn.execute(
                        f"SELECT COUNT(*) as cnt FROM thoughts WHERE {active_tags_clause} AND date_key = ?",
                        (yesterday,),
                    ).fetchone()["cnt"]
                    y_done = conn.execute(
                        f"SELECT COUNT(*) as cnt FROM thoughts WHERE status = 'done' AND {active_tags_clause} AND date_key = ?",
                        (yesterday,),
                    ).fetchone()["cnt"]

                    return self._json_response({
                        "active_count": total,
                        "completed_today": completed_today,
                        "overdue_count": overdue,
                        "next_deadline": next_deadline,
                        "yesterday_total": y_total,
                        "yesterday_completed": y_done,
                        "greeting": _time_greeting(now),
                    })
                finally:
                    conn.close()
            except Exception as e:
                return self._json_response({"error": str(e)}, 500)

        if path == "/api/routines/today":
            try:
                today = datetime.now().date()
                today_str = today.strftime('%Y-%m-%d')
                conn = get_db()
                try:
                    rows = conn.execute(
                        "SELECT r.*, t.emoji AS thought_emoji "
                        "FROM routines r LEFT JOIN thoughts t ON r.thought_id = t.id "
                        "WHERE r.status = 'active'"
                    ).fetchall()

                    routines_out = []
                    for row in rows:
                        r = dict(row)
                        sdata = json.loads(r['schedule_data']) if isinstance(r['schedule_data'], str) else r['schedule_data']
                        if not _is_scheduled_on_date(r['schedule_type'], sdata, today):
                            continue

                        completed = conn.execute(
                            "SELECT 1 FROM routine_completions WHERE routine_id = ? AND completed_date = ?",
                            (r['id'], today_str),
                        ).fetchone()

                        dots, needs_att, pct = _compute_consistency(
                            r['id'], r['schedule_type'], sdata, conn, today,
                        )

                        routines_out.append({
                            'id': r['id'],
                            'title': r['title'],
                            'schedule_type': r['schedule_type'],
                            'schedule_label': _get_schedule_label(r['schedule_type'], sdata),
                            'completed_today': bool(completed),
                            'consistency': dots,
                            'needs_attention': needs_att,
                            'consistency_pct': pct,
                            'emoji': r.get('thought_emoji') or None,
                        })

                    completed_count = sum(1 for r in routines_out if r['completed_today'])

                    paused_rows = conn.execute(
                        "SELECT * FROM routines WHERE status = 'paused' ORDER BY created_at DESC"
                    ).fetchall()
                    paused_out = []
                    for pr in paused_rows:
                        p = dict(pr)
                        psdata = json.loads(p['schedule_data']) if isinstance(p['schedule_data'], str) else p['schedule_data']
                        paused_out.append({
                            'id': p['id'],
                            'title': p['title'],
                            'schedule_type': p['schedule_type'],
                            'schedule_label': _get_schedule_label(p['schedule_type'], psdata),
                        })

                    return self._json_response({
                        'routines': routines_out,
                        'paused_routines': paused_out,
                        'total_today': len(routines_out),
                        'completed_today': completed_count,
                    })
                finally:
                    conn.close()
            except Exception as e:
                return self._json_response({"error": str(e)}, 500)

        if path == "/api/routines":
            try:
                conn = get_db()
                try:
                    rows = conn.execute(
                        "SELECT * FROM routines ORDER BY created_at DESC"
                    ).fetchall()
                    routines_out = []
                    for row in rows:
                        r = dict(row)
                        sdata = json.loads(r['schedule_data']) if isinstance(r['schedule_data'], str) else r['schedule_data']
                        total_comp = conn.execute(
                            "SELECT COUNT(*) as cnt FROM routine_completions WHERE routine_id = ?",
                            (r['id'],),
                        ).fetchone()['cnt']
                        _, _, pct = _compute_consistency(
                            r['id'], r['schedule_type'], sdata, conn,
                        )
                        routines_out.append({
                            'id': r['id'],
                            'title': r['title'],
                            'schedule_type': r['schedule_type'],
                            'schedule_data': sdata,
                            'schedule_label': _get_schedule_label(r['schedule_type'], sdata),
                            'status': r['status'],
                            'created_at': r['created_at'],
                            'consistency_pct': pct,
                            'total_completions': total_comp,
                        })
                    return self._json_response({'routines': routines_out})
                finally:
                    conn.close()
            except Exception as e:
                return self._json_response({"error": str(e)}, 500)

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
                    thought = _row_to_dict(row)
                    enrich_thought_alarm_fields([thought])
                    return self._json_response(thought)
                return self._json_response({"error": "not found"}, 404)
            except Exception as e:
                return self._json_response({"error": str(e)}, 500)

        if path == "/api/notifications":
            try:
                limit = int(qs.get("limit", ["50"])[0])
                conn = get_db()
                try:
                    rows = conn.execute(
                        "SELECT * FROM notification_events ORDER BY fired_at DESC LIMIT ?",
                        (limit,),
                    ).fetchall()
                    unread = conn.execute(
                        "SELECT COUNT(*) FROM notification_events WHERE is_read = 0"
                    ).fetchone()[0]
                finally:
                    conn.close()
                notifications = [dict(r) for r in rows]
                return self._json_response({"notifications": notifications, "unread_count": unread})
            except Exception as e:
                return self._json_response({"error": str(e)}, 500)

        self.send_error(404)

    def do_DELETE(self):
        path = urlparse(self.path).path

        m = re.match(r'^/api/notifications/(\d+)$', path)
        if m:
            try:
                notif_id = int(m.group(1))
                conn = get_db()
                try:
                    conn.execute("DELETE FROM notification_events WHERE id = ?", (notif_id,))
                    conn.commit()
                finally:
                    conn.close()
                return self._json_response({"success": True})
            except Exception as e:
                return self._json_response({"error": str(e)}, 500)

        m = re.match(r'^/api/routines/(\d+)$', path)
        if m:
            try:
                routine_id = int(m.group(1))
                conn = get_db()
                try:
                    r = conn.execute("SELECT id FROM routines WHERE id = ?", (routine_id,)).fetchone()
                    if not r:
                        return self._json_response({"error": "not found"}, 404)
                    conn.execute("DELETE FROM routine_completions WHERE routine_id = ?", (routine_id,))
                    conn.execute("DELETE FROM routines WHERE id = ?", (routine_id,))
                    conn.commit()
                finally:
                    conn.close()
                return self._json_response({"success": True})
            except Exception as e:
                return self._json_response({"error": str(e)}, 500)

        if path.startswith("/api/thoughts/"):
            try:
                thought_id = int(path.split("/")[-1])
                thought = delete_thought(thought_id)
                if not thought:
                    return self._json_response({"error": "not found"}, 404)
                try:
                    remove_from_journal(thought["created_at"], thought["text"])
                except Exception as je:
                    print(f"Journal cleanup failed: {je}")
                return self._json_response({"status": "ok", "success": True, "id": thought_id})
            except Exception as e:
                return self._json_response({"error": str(e)}, 500)

        self.send_error(404)

    def do_PUT(self):
        path = urlparse(self.path).path

        m = re.match(r'^/api/routines/(\d+)$', path)
        if m:
            try:
                routine_id = int(m.group(1))
                body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
                conn = get_db()
                try:
                    row = conn.execute("SELECT * FROM routines WHERE id = ?", (routine_id,)).fetchone()
                    if not row:
                        return self._json_response({"error": "not found"}, 404)

                    updates, params = [], []
                    if 'title' in body:
                        updates.append("title = ?")
                        params.append(body['title'])
                    if 'schedule_type' in body:
                        updates.append("schedule_type = ?")
                        params.append(body['schedule_type'])
                    if 'schedule_data' in body:
                        updates.append("schedule_data = ?")
                        params.append(json.dumps(body['schedule_data']))
                    if 'status' in body:
                        new_status = body['status']
                        updates.append("status = ?")
                        params.append(new_status)
                        now_iso = datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
                        if new_status == 'paused':
                            updates.append("paused_at = ?")
                            params.append(now_iso)
                        elif new_status == 'archived':
                            updates.append("archived_at = ?")
                            params.append(now_iso)
                        elif new_status == 'active':
                            updates.append("paused_at = NULL")
                            updates.append("archived_at = NULL")

                    if updates:
                        sql_set = ", ".join(updates)
                        params.append(routine_id)
                        conn.execute(f"UPDATE routines SET {sql_set} WHERE id = ?", params)
                        conn.commit()

                    updated = conn.execute("SELECT * FROM routines WHERE id = ?", (routine_id,)).fetchone()
                    r = dict(updated)
                    sdata = json.loads(r['schedule_data']) if isinstance(r['schedule_data'], str) else r['schedule_data']
                    return self._json_response({
                        'success': True,
                        'routine': {
                            'id': r['id'],
                            'title': r['title'],
                            'schedule_type': r['schedule_type'],
                            'schedule_data': sdata,
                            'schedule_label': _get_schedule_label(r['schedule_type'], sdata),
                            'status': r['status'],
                        },
                    })
                finally:
                    conn.close()
            except json.JSONDecodeError:
                return self._json_response({"error": "invalid json"}, 400)
            except Exception as e:
                return self._json_response({"error": str(e)}, 500)

        if path.startswith("/api/thoughts/") and path.endswith("/edit"):
            try:
                parts = path.strip("/").split("/")
                # /api/thoughts/<id>/edit
                if len(parts) != 4 or parts[0] != "api" or parts[1] != "thoughts" or parts[3] != "edit":
                    return self._json_response({"error": "not found"}, 404)

                thought_id = int(parts[2])
                body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
                new_text = body.get("text", "")
                new_priority = body.get("priority", None)

                _, payload, status = edit_thought(thought_id, new_text, new_priority_override=new_priority)
                return self._json_response(payload, status)
            except json.JSONDecodeError:
                return self._json_response({"error": "invalid json"}, 400)
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
                body_priority = body.get("priority", None)

                text, priority = extract_priority(text, manual_tags, body_priority)
                manual_tags = strip_priority_from_tags(manual_tags)

                detected = auto_tag(text)
                final_tags = merge_tags(manual_tags, detected)

                if final_tags == ["random"]:
                    ai_tags = quick_ai_classify(text)
                    if ai_tags:
                        final_tags = ai_tags
                        detected = ai_tags

                final_tags = strip_priority_from_tags(final_tags)

                thought = save_thought(text, final_tags, priority=priority)
                try:
                    write_to_journal(text, final_tags, thought["created_at"], priority=priority)
                except Exception as je:
                    print(f"Journal write failed: {je}")

                # Alarm generation (only for reminder/todo tags).
                alarm_count = 0
                alarm_zone = None
                try:
                    alarm_count, alarm_zone = insert_alarms_for_thought(
                        thought["id"],
                        text,
                        final_tags,
                        thought["created_at"],
                    )
                    if alarm_count > 0 and scheduler:
                        scheduler.wake()
                except Exception as alarm_err:
                    print(f"Alarm generation failed: {alarm_err}")

                routine_id = None
                routine_existed = False
                if "routine" in final_tags:
                    try:
                        parsed_sched = parse_routine_schedule(text)
                        # Frontend day selector takes priority over NLP parser
                        frontend_sched = body.get("routine_schedule")
                        if frontend_sched and isinstance(frontend_sched, dict):
                            stype = frontend_sched.get("type", "daily")
                            sdays = frontend_sched.get("days", [])
                            if stype == "daily":
                                parsed_sched["schedule_type"] = "daily"
                                parsed_sched["schedule_data"] = {}
                            elif stype == "weekdays":
                                parsed_sched["schedule_type"] = "weekdays"
                                parsed_sched["schedule_data"] = {}
                            elif stype == "specific_days" and sdays:
                                parsed_sched["schedule_type"] = "specific_days"
                                parsed_sched["schedule_data"] = {"days": sdays}
                        routine_id, routine_existed = save_routine(
                            thought["id"],
                            parsed_sched["title"],
                            parsed_sched["schedule_type"],
                            parsed_sched["schedule_data"],
                        )
                    except Exception as re_err:
                        print(f"Routine creation failed: {re_err}")

                resp = {
                    "thought": thought,
                    "auto_tags": [t for t in detected if t != "random"],
                    "manual_tags": manual_tags,
                    "alarm_count": alarm_count,
                    "alarm_zone": alarm_zone,
                }
                if routine_id is not None:
                    resp["routine_id"] = routine_id
                    resp["routine_existed"] = routine_existed

                self._json_response(resp, 201)
                maybe_enrich(thought)
                maybe_predict_emoji(thought)
                return
            except Exception as e:
                return self._json_response({"error": str(e)}, 500)

        m = re.match(r'^/api/routines/(\d+)/complete$', path)
        if m:
            try:
                routine_id = int(m.group(1))
                today_str = datetime.now().strftime('%Y-%m-%d')
                conn = get_db()
                try:
                    r = conn.execute("SELECT id FROM routines WHERE id = ?", (routine_id,)).fetchone()
                    if not r:
                        return self._json_response({"error": "not found"}, 404)

                    existing = conn.execute(
                        "SELECT id FROM routine_completions WHERE routine_id = ? AND completed_date = ?",
                        (routine_id, today_str),
                    ).fetchone()

                    if existing:
                        conn.execute("DELETE FROM routine_completions WHERE id = ?", (existing['id'],))
                        conn.commit()
                        return self._json_response({"completed": False})
                    else:
                        now_iso = datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
                        conn.execute(
                            "INSERT INTO routine_completions (routine_id, completed_date, completed_at) VALUES (?, ?, ?)",
                            (routine_id, today_str, now_iso),
                        )
                        conn.commit()
                        return self._json_response({"completed": True})
                finally:
                    conn.close()
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

        if path == "/api/alarms/snooze":
            try:
                body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
                alarm_id = body.get("alarm_id")
                if not alarm_id:
                    return self._json_response({"error": "alarm_id required"}, 400)

                conn = get_db()
                try:
                    alarm = conn.execute(
                        "SELECT * FROM alarms WHERE id = ?",
                        (int(alarm_id),),
                    ).fetchone()
                    if not alarm:
                        return self._json_response({"error": "Alarm not found"}, 404)

                    zone = alarm["zone"]
                    seq = int(alarm["sequence_index"])
                    snooze_count = int(alarm["snooze_count"])

                    max_snoozes = {"pinned": 1, "day_bound": 2, "soft": 1, "open_todo": 0}
                    if snooze_count >= max_snoozes.get(zone, 0):
                        return self._json_response({"error": "Max snoozes reached"}, 400)

                    if zone == "pinned":
                        snooze_mins = 5
                    elif zone == "day_bound":
                        snooze_mins = 60
                    elif zone == "soft":
                        snooze_mins = {1: 120, 2: 60, 3: 30}.get(seq, 60)
                    else:
                        return self._json_response({"error": "Open todos cannot be snoozed"}, 400)

                    new_fire = (datetime.now() + timedelta(minutes=snooze_mins)).isoformat()
                    conn.execute(
                        "UPDATE alarms SET status = 'pending', fire_at = ?, snooze_count = ?, snoozed_until = ? "
                        "WHERE id = ?",
                        (new_fire, snooze_count + 1, new_fire, int(alarm_id)),
                    )
                    conn.commit()
                finally:
                    conn.close()

                if scheduler:
                    scheduler.wake()
                return self._json_response(
                    {
                        "success": True,
                        "snoozed_until": new_fire,
                        "snooze_minutes": snooze_mins,
                    }
                )
            except Exception as e:
                return self._json_response({"error": str(e)}, 500)

        if path == "/api/alarms/dismiss":
            try:
                body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
                alarm_id = body.get("alarm_id")
                if not alarm_id:
                    return self._json_response({"error": "alarm_id required"}, 400)

                conn = get_db()
                try:
                    conn.execute(
                        "UPDATE alarms SET status = 'dismissed' WHERE id = ?",
                        (int(alarm_id),),
                    )
                    conn.commit()
                finally:
                    conn.close()
                return self._json_response({"success": True})
            except Exception as e:
                return self._json_response({"error": str(e)}, 500)

        if path == "/api/thoughts/complete":
            try:
                body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
                thought_id = body.get("thought_id")
                if not thought_id:
                    return self._json_response({"error": "thought_id required"}, 400)

                conn = get_db()
                try:
                    conn.execute(
                        "UPDATE thoughts SET status = 'done' WHERE id = ?",
                        (int(thought_id),),
                    )
                    cancel_pending_alarms(conn, int(thought_id))
                    conn.commit()
                finally:
                    conn.close()
                return self._json_response({"success": True})
            except Exception as e:
                return self._json_response({"error": str(e)}, 500)

        if path == "/api/thoughts/archive":
            try:
                body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
                thought_id = body.get("thought_id")
                if not thought_id:
                    return self._json_response({"error": "thought_id required"}, 400)

                conn = get_db()
                try:
                    conn.execute(
                        "UPDATE thoughts SET status = 'archived' WHERE id = ?",
                        (int(thought_id),),
                    )
                    cancel_pending_alarms(conn, int(thought_id))
                    conn.commit()
                finally:
                    conn.close()
                return self._json_response({"success": True})
            except Exception as e:
                return self._json_response({"error": str(e)}, 500)

        if path == "/api/thoughts/dismiss":
            try:
                body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
                thought_id = body.get("thought_id")
                if not thought_id:
                    return self._json_response({"error": "thought_id required"}, 400)

                conn = get_db()
                try:
                    conn.execute(
                        "UPDATE thoughts SET status = 'dismissed' WHERE id = ?",
                        (int(thought_id),),
                    )
                    cancel_pending_alarms(conn, int(thought_id))
                    conn.commit()
                finally:
                    conn.close()
                return self._json_response({"success": True})
            except Exception as e:
                return self._json_response({"error": str(e)}, 500)

        if path == "/api/thoughts/revive":
            try:
                body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
                thought_id = body.get("thought_id")
                if not thought_id:
                    return self._json_response({"error": "thought_id required"}, 400)

                thought_id = int(thought_id)
                conn = get_db()
                try:
                    row = conn.execute(
                        "SELECT * FROM thoughts WHERE id = ?",
                        (thought_id,),
                    ).fetchone()
                    if not row:
                        return self._json_response({"error": "Thought not found"}, 404)

                    conn.execute(
                        "UPDATE thoughts SET status = 'active' WHERE id = ?",
                        (thought_id,),
                    )
                    cancel_pending_alarms(conn, thought_id)
                    conn.commit()
                finally:
                    conn.close()

                thought = _row_to_dict(row)
                tags = thought.get("tags", [])
                alarm_tags = {"reminder", "todo", "private_reminder", "private_todo"}
                alarm_count = 0
                if alarm_tags.intersection(set(tags)):
                    now = datetime.now()
                    cfg = get_alarm_config()
                    parsed = parse_time_signal(thought["text"], now=now, config=cfg)
                    created_at = now if parsed["zone"] == "open_todo" else datetime.strptime(
                        thought["created_at"],
                        "%Y-%m-%dT%H:%M:%S",
                    )
                    alarms = generate_alarm_sequence(
                        parsed,
                        thought["text"],
                        now=now,
                        config=cfg,
                        created_at=created_at,
                        is_private=bool({"private_todo", "private_reminder"}.intersection(set(tags))),
                    )
                    if alarms:
                        conn = get_db()
                        try:
                            now_iso = now.isoformat()
                            for alarm in alarms:
                                conn.execute(
                                    "INSERT INTO alarms (thought_id, zone, sequence_index, fire_at, tone, message, created_at) "
                                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                                    (
                                        thought_id,
                                        alarm["zone"],
                                        alarm["sequence_index"],
                                        alarm["fire_at"],
                                        alarm["tone"],
                                        alarm["message"],
                                        now_iso,
                                    ),
                                )
                            conn.commit()
                            alarm_count = len(alarms)
                        finally:
                            conn.close()

                if scheduler and alarm_count > 0:
                    scheduler.wake()
                return self._json_response({"success": True, "alarm_count": alarm_count})
            except Exception as e:
                return self._json_response({"error": str(e)}, 500)

        if path == "/api/alarms/test":
            try:
                fire_notification("🔔 Test Alarm", "This is a test alarm", "gentle")
                return self._json_response({"success": True})
            except Exception as e:
                return self._json_response({"error": str(e)}, 500)

        if path == "/api/notifications/read":
            try:
                body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
                notif_id = int(body.get("id", 0))
                conn = get_db()
                try:
                    conn.execute("UPDATE notification_events SET is_read = 1 WHERE id = ?", (notif_id,))
                    conn.commit()
                finally:
                    conn.close()
                return self._json_response({"success": True})
            except Exception as e:
                return self._json_response({"error": str(e)}, 500)

        if path == "/api/notifications/read-all":
            try:
                conn = get_db()
                try:
                    conn.execute("UPDATE notification_events SET is_read = 1")
                    conn.commit()
                finally:
                    conn.close()
                return self._json_response({"success": True})
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
    global scheduler

    DATA_DIR.mkdir(exist_ok=True)
    JOURNAL_DIR.mkdir(exist_ok=True)
    init_db()

    scheduler = AlarmScheduler(DB_PATH)
    scheduler.start()
    print("Alarm scheduler started")

    host = "0.0.0.0"
    api_server = ThreadingHTTPServer((host, API_PORT), APIHandler)
    frontend_server = ThreadingHTTPServer((host, FRONTEND_PORT), FrontendHandler)

    def shutdown(sig, frame):
        print("\nShutting down...")
        if scheduler:
            scheduler.stop()
        threading.Thread(target=api_server.shutdown, daemon=True).start()
        threading.Thread(target=frontend_server.shutdown, daemon=True).start()

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
