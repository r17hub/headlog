# Headlog — Project Rules

## Core Rules

- **No page-level scrolling.** Every view must fit entirely within the viewport (100vh). No layout change (expanding panels, revealing private items, toggling sections) should ever cause the page to scroll. Internal scroll within bounded containers (e.g., browse thought list, chat messages) is fine — page-level scroll is not.
- **Text field position is sacred.** The capture text box must never shift, jump, or reposition due to side panel changes (private item reveals, content loading, etc.). Side panels are independent — they can resize internally, but the text field stays fixed in place.
- **Zero external dependencies.** Python standard library only. Frontend is plain HTML/CSS/JS — no npm, no frameworks, no build step.
- **Dual storage.** Every thought is saved to both SQLite and Markdown journal files simultaneously. Deletes must clean up both.
- **Private tags are manual-only.** The keyword scanner and AI enrichment never auto-assign `#private_todo` or `#private_reminder`.

## Architecture

- `app.py` — single-file Python server (API on :5959, frontend on :7777)
- `frontend/` — static HTML/CSS/JS served directly
- `data/thoughts.db` — SQLite with FTS5 full-text search
- `data/journal/YYYY/MM/YYYY-MM-DD.md` — daily markdown files
- See `docs/Headlog-Product-Document.md` for full product spec
