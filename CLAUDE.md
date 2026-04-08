---
description: 
alwaysApply: true
---

# Headlog — Project Rules

## Core Rules

- **No page-level scrolling.** Every view must fit entirely within the viewport (100vh). No layout change (expanding panels, revealing private items, toggling sections) should ever cause the page to scroll. Internal scroll within bounded containers (e.g., browse thought list, chat messages) is fine — page-level scroll is not.
- **Text field position is sacred.** The capture text box must never shift, jump, or reposition due to side panel changes (private item reveals, content loading, etc.). Side panels are independent — they can resize internally, but the text field stays fixed in place.
- **Zero external dependencies.** Python standard library only. Frontend is plain HTML/CSS/JS — no npm, no frameworks, no build step.
- **Dual storage.** Every thought is saved to both SQLite and Markdown journal files simultaneously. Deletes must clean up both.
- **Private tags are manual-only.** The keyword scanner and AI enrichment never auto-assign `#private_todo` or `#private_reminder`.
- **Thought statuses:** `active` (default), `done` (checkbox completed), `archived` (user removed from list), `dismissed` (reminder cleared after time passed), `expired` (auto-expired by system after 24h with no pending alarms), `stale` (open todo final alarm fired). Capture screen widgets show only `active` (reminders) or `active` + `stale` (todos). Browse Thoughts shows all statuses.
- **Swipe-to-dismiss:** Right swipe on reminder cards → `dismissed`. Right swipe on todo cards → `archived`. Desktop fallback: `×` button on hover.
- **Auto-expiry:** Reminders older than 24h with no pending alarms are auto-transitioned to `expired` by the alarm scheduler (runs hourly).
- **Priority is metadata, not a tag.** P0/P1/P2 are stored in the `priority` column (TEXT, nullable), not in the `tags` JSON array. Entered via `#p0` inline (stripped from text) or via chip/API body field. Never auto-assigned by keyword scanner or AI enrichment.
- **Priority colors:** P0 = Deep Violet #5B21B6, P1 = Steel Blue #1D4ED8, P2 = Soft Teal #0F766E.
- **Urgency colors** (time-to-deadline, 3px left border): Green #16a34a (>6h), Yellow #ca8a04 (2–6h), Orange #ea580c (30min–2h), Red #dc2626 (<30min/overdue), Muted #B0A99F (open todo).
- **Journal format with priority:** `### 14:32:07  [P0] #reminder, #career`

## Architecture

- `app.py` — single-file Python server (API on :5959, frontend on :7777)
- `frontend/` — static HTML/CSS/JS served directly
- `data/thoughts.db` — SQLite with FTS5 full-text search
- `data/journal/YYYY/MM/YYYY-MM-DD.md` — daily markdown files
- See `docs/Headlog-Product-Document.md` for full product spec
