# Headlog — Product Document

**Version:** 1.1
**Date:** March 23, 2026
**Status:** Personal tool (potential product later)
**Tagline:** A raw dump of what's in your head.

---

## 1. The problem

Every day, thoughts arrive — some are tiny, some are life-changing, most are somewhere in between. An idea for a side project. A reminder about a meeting. A reflection on a pattern you noticed in your own behavior. A plan for next year. A random observation about penguins.

The problem is not having thoughts. The problem is the friction between having a thought and capturing it.

When a thought arrives, you face a cascade of micro-decisions that kill the moment:

- **Which app?** Notes, Notion, Google Docs, a random text file, WhatsApp messages to yourself...
- **Which folder?** Ideas? Plans? Random? Health? Do I create a new one?
- **What format?** Do I title this? Tag it? Just dump text? Start a new document?

By the time you've decided where to put it, the thought has either lost its sharpness or you've abandoned the effort entirely. The friction of organization defeats the purpose of capture.

The result: thoughts are lost. Not because you forgot them, but because the system made it too hard to save them. Over months and years, this compounds — you lose patterns you would have noticed, connections you would have made, and a record of your own intellectual and emotional evolution.

---

## 2. The soul of the project

**Reduce the distance between having a thought and capturing it to absolute zero. Then let intelligence emerge from the accumulated text over time.**

Open Headlog. Dump what's in your head. Close it. Three seconds. Done.

No titles, no folders, no decisions. Just a raw log of everything that passes through your mind — the silly stuff, the brilliant stuff, the plans, the rants, the questions, the reminders. All of it, captured without friction.

Behind that single text box, the system handles everything: timestamping, categorizing, organizing into files, indexing for search, and enriching with AI — all silently, all instantly, all without you thinking about it.

The user never sees folders, files, categories, or databases. They see a text box. They type. They move on with their life. Intelligence accumulates behind the scenes.

---

## 3. Design philosophy

### 3.1 Zero friction capture

The primary interaction — entering a thought — must feel as effortless as breathing. No login, no page load, no decisions. The text box is always there, always empty, always ready. You type, you save, you continue with your day. The system is a utility, not an application. It should feel like Spotlight on a Mac — summoned instantly, used briefly, dismissed without thought.

### 3.2 Intelligence emerges, not imposed

The system does not ask you to organize. It does not require you to categorize. It does not force you to tag. Instead, it observes what you write and applies structure automatically — through keyword detection, through AI analysis, through temporal organization. You can manually tag if you want to (and sometimes you should), but the system works perfectly without any manual effort.

### 3.3 Simplicity as durability

This tool should work five years from now without maintenance. That means no dependencies that break on update, no cloud services that shut down, no build pipelines that rot. One file to run, zero packages to install, data stored in formats (plain text, SQLite) that will be readable for decades. The technology choices are deliberately boring because boring technology is reliable technology.

### 3.4 Privacy by default

Your thoughts are possibly the most personal data you produce. The system runs entirely on your machine. Nothing leaves your computer unless you explicitly choose it (like syncing via Google Drive). There is no cloud server, no account, no authentication, no analytics, no telemetry.

### 3.5 Progressive capability

The system works with zero configuration — just run it and start typing. Each additional capability (AI chat, tag enrichment, cloud sync, iPhone access) is an optional layer that adds value without being required. You can use it for a year with nothing but the text box and search, and it's still valuable.

---

## 4. Target user

This is built for one person: me. It's a personal enhancement tool, not a product (though it could become one later). The assumptions are:

- Uses a MacBook as the primary device
- iPhone is secondary (nice to have, not essential)
- Comfortable with Terminal (can run `python3 app.py`)
- Has a Claude Pro subscription (for Claude Code CLI)
- Wants something that runs forever on localhost without maintenance
- Types thoughts throughout the day — anywhere from 5 to 50 per day
- Wants to recall and reflect on past thoughts using AI
- Doesn't want to manage files, folders, or databases manually

---

## 5. System architecture

### 5.1 High-level overview

The system has three layers:

**Input layer** — A web-based UI served on localhost. Single text box with optional manual tag chips. Accessible from any browser on the same machine, or from iPhone on the same WiFi network.

**Backend layer** — A Python server that handles saving, tagging (3-layer hybrid), storing to dual storage (SQLite + Markdown), and serving the AI chat endpoint.

**Retrieval layer** — Three tiers of intelligence for querying your thoughts, from instant keyword search to full AI-powered analysis.

### 5.2 Data flow

When you type a thought and hit save:

1. **Timestamp captured** — exact date and time logged (e.g., 2026-03-22T14:32:07)
2. **Manual tags locked in** — any chips you tapped are included first (highest trust)
3. **Keyword scanner fires** — Python scans ~130 keywords across 23 categories, merges with manual tags, deduplicates (0ms)
4. **Saved to SQLite** — text, tags, timestamp, word count stored as a row. FTS5 trigger auto-updates the full-text search index (instant)
5. **Saved to Markdown** — appended to the daily journal file (e.g., `data/journal/2026/03/2026-03-22.md`) with timestamp and tags as header
6. **AI enrichment fires in background** — if Ollama or Gemini is configured, a background thread sends the thought to the AI for nuanced tag suggestions. Results merge silently into the database 2-5 seconds later. Non-blocking, best-effort, fails gracefully.
7. **Toast notification** — user sees a brief confirmation with the applied tags. Input resets, ready for the next thought.

Total time from typing to saved: under 100ms for the user-facing flow. The AI enrichment happens after the user has already moved on.

---

## 6. Tooling decisions

### 6.1 Server: Python standard library

**Chosen because:** Pre-installed on every Mac. Zero dependencies — no pip installs, no virtual environments, no package managers. The entire application is a single Python file using only built-in modules (`http.server`, `sqlite3`, `json`, `threading`, `pathlib`, `re`, `urllib`). It runs with `python3 app.py` and nothing else.

**Rejected alternatives:**
- **Next.js / Node.js** — requires npm, build step, 400+ transitive dependencies, breaks on updates. Massive overkill for a single-user localhost tool.
- **Flask / FastAPI** — requires pip install, virtual environment management. Adds moving parts for minimal benefit over the standard library.
- **Go / Rust** — requires compilation, separate toolchain. Python is already there.

### 6.2 Frontend: Plain HTML, CSS, JavaScript

**Chosen because:** No build step. No bundler. No JSX compilation. No framework. Python serves static files from a `frontend/` folder. Works in every browser including iPhone Safari. Can be edited with full syntax highlighting in any editor.

**Rejected alternatives:**
- **React / Vue / Svelte** — requires Node.js, npm, build pipeline, development server. For a personal tool with one user, a framework adds complexity without adding capability.
- **Electron** — 200MB+ application for what a browser tab does. Absurd for this use case.

### 6.3 Database: SQLite

**Chosen because:** SQLite is a single file, not a server. There's no process running in the background, no ports, no passwords, no configuration. Python has it built in. It handles millions of rows trivially — 50 thoughts per day for 30 years would be ~550,000 entries, which SQLite manages in microseconds. It includes FTS5, a full-text search engine, which powers instant search across all thoughts.

**Rejected alternatives:**
- **PostgreSQL** — requires a separate server running 24/7, connection management, configuration, migrations. The right choice for a product serving thousands of users. Pure overhead for one person on one machine.
- **MongoDB** — requires installation, a running server process. The data is perfectly structured (text, tags, timestamp) — NoSQL flexibility adds nothing.
- **JSON files** — no search capability, no indexing, doesn't scale. Fine for 100 entries, unusable at 10,000.

### 6.4 Backup: Markdown files + Google Drive

**Chosen because:** Markdown is the most future-proof text format that exists. In 10 years, every text editor will still read it. The daily journal files (`2026-03-22.md`) are human-readable, organized by date, and serve as a backup independent of the database. Claude Code CLI reads these files directly for deep analysis. Placing the project folder inside Google Drive provides automatic cloud sync with zero code.

**Rejected alternatives:**
- **Custom cloud sync** — requires code to write, conflict resolution to handle, authentication to manage.
- **S3 / Firebase** — requires an account, API setup, billing configuration, authentication. All for backing up a few kilobytes of text per day.

### 6.5 AI (quick search): Ollama with llama3.2:3b

**Chosen because:** Free, local, fast, no internet needed. The 3B parameter model uses ~2GB disk and ~3GB RAM only while active (releases memory after a few minutes of inactivity). For the primary use case — "find my thoughts about X" and "what did I say about health?" — a small model reading provided context performs very well (~90% accuracy). No API key, no rate limits, no cost.

**Rejected alternatives:**
- **GPT-4 / Claude API** — per-token cost for every query. For a tool used 10-30 times per day, costs accumulate unnecessarily when a local model handles the simple queries adequately.
- **Larger models (7B+)** — heavier resource usage for marginal improvement on simple text retrieval tasks. The 3B model is the right size for this specific workload.

### 6.6 AI (deep analysis): Claude Code CLI

**Chosen because:** Already paid for through the Claude Pro subscription ($20/month). Claude Code reads local files directly — it can open the markdown journal files, query the SQLite database, and synthesize across months of thoughts with Opus/Sonnet-level intelligence. No API key to manage, no extra cost, no token counting. The `CLAUDE.md` file in the project acts as a permanent briefing document that tells Claude exactly where data lives and how to search it.

**Rejected alternatives:**
- **Custom RAG pipeline** — LangChain, embeddings, vector database, chunking strategies. A massive engineering effort that solves the same problem Claude Code handles out of the box.
- **Claude API separately** — extra cost when Claude Code is already included in Pro. API would also require building a custom integration.

### 6.7 iPhone access: Safari "Add to Home Screen"

**Chosen because:** When the Python server runs on localhost, any device on the same WiFi can access it via the Mac's local IP. Opening this URL in Safari and choosing "Add to Home Screen" creates a full-screen web app icon that looks and behaves like a native app. Zero maintenance, zero certificates, zero cost.

**Rejected alternatives:**
- **Native iOS app** — requires Xcode, Swift/SwiftUI, a $99/year Apple Developer account (or AltStore with 7-day refresh cycles for sideloading). Enormous effort for what a pinned browser tab achieves.
- **React Native / Flutter** — full mobile framework to build a single text input screen. Absurd for this use case.

### 6.8 Always running: macOS LaunchAgent

**Chosen because:** macOS has a built-in system (`launchd`) for managing background services. A small `.plist` configuration file tells the system to start Headlog on login and restart it if it ever crashes. This is the same mechanism Apple uses for its own background services — it's the right tool for "always available on localhost."

**Rejected alternatives:**
- **Docker** — requires Docker Desktop installation, daemon running, container management. Adds a layer of abstraction for zero benefit on a single machine.
- **Cron job** — not designed for long-running services, doesn't handle restarts.
- **Manual startup** — fragile, forgettable.

---

## 7. Data architecture

### 7.1 Dual storage strategy

Every thought is stored in two places simultaneously:

**SQLite database (`data/thoughts.db`)** — purpose: speed. Handles full-text search, tag filtering, statistical queries, and counting. The FTS5 virtual table enables instant search across all thoughts. Schema:

| Column | Type | Purpose |
|--------|------|---------|
| id | INTEGER (PK) | Auto-incrementing unique ID |
| text | TEXT | The raw thought content |
| tags | TEXT (JSON) | Array of tag strings, e.g. `["health", "routine"]` |
| created_at | TEXT (ISO) | Full timestamp, e.g. `2026-03-22T14:32:07` |
| date_key | TEXT | Date only, e.g. `2026-03-22` (for date range queries) |
| word_count | INTEGER | Word count of the thought |
| is_private | INTEGER | 1 if any private tag is present, 0 otherwise (for fast UI filtering) |

**Markdown journal files (`data/journal/YYYY/MM/YYYY-MM-DD.md`)** — purpose: durability and readability. One file per day, auto-created. Human-readable in any text editor. Claude Code CLI reads these directly for deep analysis. Format:

```
# Thoughts — Saturday, March 22, 2026

### 14:32:07  #health, #routine
I should start waking up at 5am and stretch every morning

---

### 16:45:22  #reminder, #career
Meeting with Raj today at 4pm about the new project scope

---
```

### 7.2 Why both?

SQLite and Markdown serve different consumers. SQLite serves the application (fast programmatic queries). Markdown serves the human (readable without any software) and Claude Code (reads files directly from disk). If SQLite ever corrupts (extremely rare), the markdown files are a complete, readable backup. If the markdown files are lost, SQLite contains everything needed to reconstruct them.

### 7.3 Storage projections

Thoughts are short text. Even with heavy daily usage:

| Usage level | Thoughts/day | After 1 year | After 5 years |
|-------------|-------------|--------------|---------------|
| Light | 5-10 | ~3,000 entries, ~500 KB | ~15,000 entries, ~2.5 MB |
| Moderate | 15-30 | ~8,000 entries, ~1.5 MB | ~40,000 entries, ~7 MB |
| Heavy | 30-50 | ~15,000 entries, ~3 MB | ~75,000 entries, ~15 MB |

SQLite handles millions of rows. Storage is never a concern.

### 7.4 Cloud sync

The entire `headlog/` folder can be placed inside a Google Drive directory on Mac. Google Drive automatically syncs all files — markdown journals, SQLite database, configuration — to the cloud. The journal files become readable from any device via the Google Drive app. No custom sync code, no API integration, no conflict resolution.

---

## 8. Tagging system

### 8.1 Design principle

No single tagging approach is trustworthy alone. Keywords are fast but dumb. AI is smart but slow and sometimes wrong. Manual input is accurate but adds friction. The three layers compensate for each other's weaknesses, and each layer is independently optional.

### 8.2 Layer 1: Manual tag chips (0ms, user-controlled)

Tappable pill-shaped buttons below the text input. 8 most-used tags visible by default, with a "show all" toggle to reveal all 23. Multi-select — tap to toggle. Completely optional — if you skip them, auto-detection handles everything. Selected chips reset after each save. The 2 private tags (`#private_todo`, `#private_reminder`) appear only inside the expanded "show all" view with a 🔒 icon and auto-dismiss after 3 seconds (see §8.8).

The 8 default visible chips are: reminder, todo, idea, decision, question, health, finance, career. These are configurable in Settings.

### 8.3 Layer 2: Keyword scanner (0ms, deterministic)

A Python function that scans the thought text against ~130 predefined keywords mapped to 23 categories. Uses word-boundary matching for short keywords (so "art" doesn't match "start") and substring matching for longer phrases.

### 8.4 The 23 tag categories

| Tag | Purpose | Example keywords |
|-----|---------|-----------------|
| `routine` | Daily life, habits, morning/night | routine, morning, evening, habit, wake up, alarm |
| `health` | Fitness, nutrition, sleep, mental health | exercise, workout, protein, sleep, meditate, stretch, doctor |
| `finance` | Money, budget, investments, expenses | money, budget, invest, salary, tax, crypto, stock, spending |
| `idea` | Business ideas, brainstorms, side projects | idea, what if, brainstorm, startup, side project, launch |
| `career` | Professional growth, job, promotion | career, promotion, interview, resume, leadership, networking |
| `learning` | Books, courses, skills, study | learn, study, course, book, read, tutorial, research, podcast |
| `tech` | Coding, tools, software, AI | code, python, api, software, deploy, bug, github, machine learning |
| `productivity` | Systems, workflows, efficiency | productive, workflow, optimize, focus, deep work, procrastinate, time block |
| `spiritual` | Philosophy, meaning, mindfulness | spiritual, mindful, soul, purpose, prayer, philosophy, stoic, presence |
| `reflection` | Self-awareness, patterns noticed | reflect, realize, notice, pattern, insight, awareness, tendency |
| `gratitude` | Appreciation, thankfulness | grateful, thankful, appreciate, blessed, fortunate, glad |
| `vent` | Frustrations, complaints, stress | frustrated, angry, sick of, tired of, unfair, disappointed |
| `lesson` | Regrets, mistakes, wisdom | lesson, regret, mistake, learned, never again, next time, should have |
| `decision` | Dilemmas, weighing options | decide, should i, dilemma, torn between, pros and cons, trade-off |
| `question` | Curiosity, things to look up | wonder, curious, how does, why does, look up, research later |
| `todo` | Open-ended tasks, action items | todo, action item, follow up, need to, have to, must, pending |
| `reminder` | Time-bound one-off items | remind, meeting, appointment, today, tomorrow, deadline, urgent, by friday |
| `people` | Connections, follow-ups, relationships | met someone, follow up with, call, reach out, catch up, friend, family |
| `selfhelp` | Self-improvement, discipline, growth | improve, discipline, willpower, growth, confidence, accountability, mindset |
| `travel` | Trips, bucket list, experiences | travel, trip, vacation, flight, bucket list, adventure, trek, hike |
| `private_todo` | Private open-ended tasks (personal/relationship) | 🔒 Manual-only — no keyword auto-detection (see §8.8) |
| `private_reminder` | Private time-bound items (personal/relationship) | 🔒 Manual-only — no keyword auto-detection (see §8.8) |
| `random` | Fallback when nothing matches | (no keywords — assigned when no other tag matches) |

### 8.5 Layer 3: AI enrichment (2-5s, background)

After the thought is saved with keyword tags, a background thread sends the text to the configured AI provider (Ollama, Gemini, or Anthropic). The AI reads the meaning and suggests additional tags from the valid set of 23. Results are validated (only tags from the valid set accepted), merged with existing tags (no duplicates), and silently updated in the database. Note: the AI enrichment layer never auto-assigns `#private_todo` or `#private_reminder` — these are manual-only tags (see §8.8).

This layer catches what keywords miss. For example, "I keep noticing I procrastinate when tasks feel ambiguous" gets `#productivity` and `#reflection` from keywords, but the AI might also add `#selfhelp` or `#lesson`. If no AI is configured, this layer simply doesn't run — keyword tags work perfectly on their own.

### 8.6 Tag merge logic

Tags from all three layers are merged with the following rules:

1. Manual tags come first (highest trust, user intent is explicit)
2. Keyword auto-tags are appended (deduplicated)
3. AI enrichment tags are appended later (deduplicated)
4. If the merged result contains any real tag, `#random` is removed
5. If no tags match from any layer, `#random` is assigned as fallback

### 8.7 Distinction: #todo vs #reminder

These two tags serve different purposes and are deliberately separated:

- **#todo** — open-ended tasks with no specific time. "Fix the login bug." "Read that book on stoicism." "Refactor the database module." These are things to do eventually.
- **#reminder** — time-bound one-off items. "Meeting today at 4pm." "Dentist tomorrow at 11am." "Submit tax form by Friday." These are things attached to a specific time.

This separation is intentional — it future-proofs the system for a notification/reminder feature. When that's built, `#reminder` tagged thoughts provide a clean query surface for extracting time-sensitive items, while `#todo` items remain in the open tasks list.

### 8.8 Private tags: #private_todo and #private_reminder

These are a special class of tags designed for thoughts you want to capture but keep discreet — things for your girlfriend, close friends, personal gifts, surprises, or anything you'd rather not have visible at a glance in the UI.

**How they differ from regular tags:**

- **Not in the default visible chips.** The 8 default chips on the capture screen do not include private tags. They only appear inside the "show all" expanded view, displayed with a 🔒 lock icon instead of the standard tag color pill.
- **Peek-to-reveal in the "show all" panel.** When you tap "show all" to expand the full tag list, `#private_todo` and `#private_reminder` appear as lock-icon chips. Tapping one selects it (same as any tag), but the chip auto-dismisses after 3 seconds — the "show all" panel collapses back, and the selected private tag is shown only as a small 🔒 icon next to the input (not the tag name). This prevents someone glancing at your screen from seeing the tag label.
- **Hidden text in Explore.** Thoughts tagged with a private tag are included in search results and tag filters, but their text content is replaced with "🔒 Private thought" in the thought card. Tapping the card reveals the full text for 3 seconds, then it re-hides. This is a soft privacy layer — not encryption, but discretion.
- **No keyword auto-detection.** The keyword scanner (Layer 2) never assigns private tags. They are manual-only — you must deliberately tap the chip. This prevents the system from accidentally flagging a thought as private based on keyword overlap.
- **No AI auto-assignment.** The AI enrichment layer (Layer 3) also never assigns private tags. The valid tag set passed to the AI excludes `#private_todo` and `#private_reminder`.
- **Storage is identical.** Private-tagged thoughts are stored in SQLite and Markdown exactly like any other thought. The privacy is a UI-level behavior, not a data-level separation. In the markdown journal files, private tags appear normally (e.g., `### 14:32:07  #private_reminder, #people`). This means Claude Code CLI can still read and analyze them — the privacy is from shoulder-surfers, not from your own tools.

**Why not just one `#private` tag?**

The same reasoning as #todo vs #reminder applies here. Separating `#private_todo` (open-ended: "buy her that book she mentioned") from `#private_reminder` (time-bound: "anniversary dinner reservation by Thursday") future-proofs these for the reminder notification feature. Private reminders can be surfaced as private notifications, while private todos stay in a filtered private task list.

**Example usage:**
- "Order flowers for Mom's birthday next week" → tap 🔒 `#private_reminder`
- "That coffee table book Priya mentioned wanting" → tap 🔒 `#private_todo`
- "Plan a surprise trip to Rishikesh for her birthday in June" → tap 🔒 `#private_todo`, `#travel`

---

## 9. UI architecture

### 9.1 Desktop layout: everything visible

On desktop, there are no top-level tabs. Everything lives on a single dashboard screen in a 3-column grid layout:

**Left column (340px):**
- Capture input (text box + save button + keyboard shortcut)
- Manual tag chips (8 default + "show all" toggle)
- Reminders widget (recent #reminder thoughts, grouped by today/tomorrow/this week)
- Open todos widget (recent #todo thoughts, with checkboxes to mark done)
- Stats bar (total thoughts, today count, word count, streak)

**Center column (flexible):**
- Search bar (full-text search with live filtering)
- Tag filter pills (clickable category pills with counts)
- Thought cards list (scrollable, each card shows timestamp, tags, text, highlighted search matches)

**Right column (320px):**
- AI chat panel (message thread + input + send button)
- Active model indicator badge (shows "Ollama 3B" or "Gemini Flash")

**Settings:** Slides in as a right-side drawer overlay when the gear icon is clicked. Not a page, not a tab — it overlays and dismisses.

### 9.2 Mobile layout: tabbed

On iPhone (and narrow screens), the layout collapses into tabs since screen width can't support the 3-column grid. The tabs are: Capture, Explore, Chat, Settings. Each tab shows the relevant components stacked vertically.

### 9.3 UI components breakdown

| Component | File | Purpose |
|-----------|------|---------|
| Thought input box | `capture-input.js` | Textarea + word count + save button + ⌘+Enter shortcut |
| Manual tag chips | `tag-chips.js` | 23 tappable pills, 8 visible by default, 2 private with 🔒 icon, multi-select, toggle |
| Dashboard stats | `stats-bar.js` | Total thoughts, today count, word count, streak display |
| Reminders widget | `reminders-widget.js` | Shows recent #reminder thoughts, auto-filtered, time-grouped |
| Open todos widget | `todos-widget.js` | Shows recent #todo thoughts, checkbox to mark as done |
| Search bar | `search-bar.js` | Full-text search input with live results |
| Tag filter bar | `tag-filters.js` | Clickable tag pills with counts for filtering |
| Thought card | `thought-card.js` | Single thought display — timestamp, tags, text, search highlights. Private thoughts show "🔒 Private thought" with tap-to-reveal (3s) |
| Chat messages | `chat-messages.js` | Scrollable AI chat message thread |
| Chat input | `chat-input.js` | Input + send button + active model badge |
| Settings: AI model | `settings-model.js` | Radio buttons for provider, model name, API key, test connection |
| Settings: Tags | `settings-tags.js` | Tag list, reorder defaults, add custom tags, edit keywords |
| Settings: Data | `settings-data.js` | Stats, DB size, export as JSON, backup info |

### 9.4 Design direction

Warm editorial minimalism. The tool should feel like a personal leather notebook, not a SaaS dashboard.

- **Typography:** Lora (serif) for thought text — gives journal-like warmth. Outfit (sans-serif) for UI elements — clean, modern, readable.
- **Color palette:** Cream/warm white backgrounds (#FAF8F5, #F6F4F0). Terracotta accent (#C05A38) for primary actions and selected states. Muted earth tones for secondary elements.
- **Each tag category has its own color** — teal for health, purple for ideas, coral for reminders, amber for finance, etc. Color-coded pills make scanning the thought stream fast. Private tags use a muted slate/charcoal with the 🔒 icon instead of a category color.
- **Spacing:** Generous whitespace. The interface breathes. Nothing feels cramped.
- **Animations:** Subtle fade-up on card appearance. Smooth transitions on chip selection. Toast notification slides in and out. Settings drawer slides from right.
- **Interaction model:** Keyboard-first for capture (⌘+Enter to save). Click/tap for everything else. No drag-and-drop except for tag reordering in settings.

---

## 10. Retrieval system

### 10.1 Three tiers

The system provides three ways to query your thoughts, each optimized for different question types:

**Tier 1: Built-in search (Explore section, 0ms, no AI)**

SQLite full-text search. Type in the search bar, results filter live. Click a tag pill to filter by category. Browse by scrolling. This is the workhorse for quick lookups — "show me everything tagged #reminder" or "search for protein."

Powered by: SQLite FTS5 (built into Python, zero setup).

**Tier 2: Ollama chat (Chat panel, 1-3s, local AI)**

A small language model reads your recent thoughts as context and answers natural language questions. Good for: "what did I say about nutrition this week?" or "list my recent ideas." The model receives your thoughts as grounding context, so it retrieves rather than generates — reducing hallucination.

Powered by: Ollama + llama3.2:3b. Free, local, ~2GB disk, ~3GB RAM while active.

Accuracy for direct recall questions: ~90%. For complex synthesis: ~70%. This tier handles 80% of daily queries.

**Tier 3: Claude Code CLI (Terminal, 5-15s, Opus quality)**

Full Claude intelligence reading your actual markdown journal files from disk. For deep questions: "how has my thinking about career evolved over the past 3 months?" or "what patterns do you see in my recent reflections?" or "summarize my month."

Powered by: Claude Code CLI (included in Pro plan, $0 extra). The `CLAUDE.md` file in the project tells Claude exactly where data lives and how to search it. The `ask` shell script provides a one-liner shortcut.

Usage: `./ask "what recurring themes do you see in my thoughts?"` or open interactive mode with `claude` in the project directory.

### 10.2 When to use which

| Question type | Tier | Example |
|---------------|------|---------|
| Keyword lookup | 1 (Search) | "Show me all #finance thoughts" |
| Date browsing | 1 (Search) | "What did I write yesterday?" |
| Direct recall | 2 (Ollama) | "What did I say about nutrition?" |
| Topic listing | 2 (Ollama) | "List my ideas from this week" |
| Pattern analysis | 3 (Claude Code) | "How has my thinking evolved?" |
| Monthly summary | 3 (Claude Code) | "Summarize March for me" |
| Cross-referencing | 3 (Claude Code) | "Any plans I mentioned but haven't followed up on?" |

### 10.3 Hallucination management

The primary use case (Tier 2 with Ollama) is grounded generation — the model receives your actual thoughts as context and extracts/summarizes from them. This is fundamentally different from open-ended generation and has much lower hallucination risk.

However, small models can still stumble:
- They may slightly paraphrase your words in ways that shift meaning
- They may provide a vaguely related answer instead of saying "I didn't find anything"
- Complex multi-month synthesis can miss nuance

Mitigation: For questions requiring high accuracy or deep analysis, use Tier 3 (Claude Code), which provides Opus/Sonnet quality with full file access.

---

## 11. Folder structure

```
headlog/
│
├── app.py                     ← Server + API routes + tagging engine + DB
├── CLAUDE.md                  ← Briefing file for Claude Code CLI
├── ask                        ← Shell shortcut: ./ask "your question"
├── README.md                  ← Setup instructions
│
├── frontend/                  ← Everything the browser sees
│   ├── index.html             ← Shell: header, column layout, section containers
│   ├── css/
│   │   ├── base.css           ← Variables, reset, typography, layout grid
│   │   ├── components.css     ← Cards, chips, buttons, inputs, toasts, badges
│   │   └── pages.css          ← Capture, explore, chat, settings section styles
│   └── js/
│       ├── app.js             ← Init, shared state, responsive layout switching
│       ├── capture/
│       │   ├── capture-input.js
│       │   ├── tag-chips.js
│       │   ├── stats-bar.js
│       │   ├── reminders-widget.js
│       │   └── todos-widget.js
│       ├── explore/
│       │   ├── search-bar.js
│       │   ├── tag-filters.js
│       │   └── thought-card.js
│       ├── chat/
│       │   ├── chat-messages.js
│       │   └── chat-input.js
│       └── settings/
│           ├── settings-model.js
│           ├── settings-tags.js
│           └── settings-data.js
│
└── data/                      ← Auto-generated, never edit manually
    ├── thoughts.db            ← SQLite database (created on first run)
    ├── config.json            ← Optional: AI provider settings (managed via Settings UI)
    └── journal/               ← Markdown files organized by date
        ├── 2026/
        │   ├── 03/
        │   │   ├── 2026-03-20.md
        │   │   ├── 2026-03-21.md
        │   │   └── 2026-03-22.md
        │   └── 04/
        │       └── ...
        └── 2027/
            └── ...
```

**You create (once):** app.py, CLAUDE.md, ask, README.md, and the frontend/ directory with all HTML/CSS/JS files.

**Auto-generated (never touch):** The entire data/ directory — thoughts.db, journal folders, and daily .md files. These appear and grow as you use the system.

**After 1 year of use:** ~365 markdown files, ~1-5 MB total storage. The project folder structure never gets more complex than what's shown above.

---

## 12. "Always running" setup

### 12.1 macOS LaunchAgent

A `.plist` configuration file tells macOS to:
- Start Headlog automatically when you log in
- Restart it automatically if it ever crashes
- Run it as a background service (no terminal window needed)

Setup is a one-time copy of the file to `~/Library/LaunchAgents/` and a single `launchctl load` command.

### 12.2 Access points

| Device | How to access | Requirement |
|--------|--------------|-------------|
| MacBook (browser) | `http://localhost:5959` | App running |
| MacBook (terminal) | `cd headlog && claude` or `./ask "..."` | Claude Code installed |
| iPhone | `http://[mac-ip]:5959` → Add to Home Screen | Same WiFi, app running |

### 12.3 Server behavior

- Listens on `0.0.0.0:5959` (accessible from all devices on the same network)
- Prints the local IP on startup for iPhone access
- Logs to `/tmp/headlog.log` when running via LaunchAgent
- Graceful shutdown on Ctrl+C or system sleep

---

## 13. Settings system

Settings are managed through a UI drawer (not by editing JSON files) and saved to `data/config.json`.

### 13.1 AI provider configuration

Radio button selection between:
- **Ollama (local)** — model name input (default: `llama3.2:3b`), test connection button
- **Gemini (free API)** — model name input, API key field, test connection button
- **Anthropic (paid API)** — model name input, API key field, test connection button
- **None (disabled)** — keyword tagging only, chat tab disabled

### 13.2 Tag chip configuration

- View all 23 tags (including 2 private tags)
- Drag to reorder which 8 appear as default visible chips on the capture screen
- Add custom tags (with custom keyword lists)
- Edit keywords associated with any tag

### 13.3 Data management

- Display total thought count, total word count, database file size
- Export all thoughts as JSON
- Open data folder in Finder
- Backup status (Google Drive sync indicator, if applicable)

---

## 14. Future possibilities

These are not planned features — they're ideas that the current architecture cleanly supports if the need arises:

- **Reminder notifications** — the #reminder tag with time-bound keywords (today, tomorrow, by Friday) provides a clean extraction surface. Add a time parser and a macOS notification scheduler.
- **Daily/weekly digest** — automated summary of the day's or week's thoughts, generated by AI and delivered as a notification or email.
- **Thought analytics** — tag frequency over time, word count trends, streak tracking, mood analysis (sentiment detection on #vent vs #gratitude ratio).
- **Multi-device sync** — if Google Drive sync isn't sufficient, a lightweight sync mechanism using the markdown files as the source of truth.
- **Voice input** — add a microphone button that uses the browser's Web Speech API for voice-to-text capture.
- **Collaborative mode** — if this becomes a product, separate user accounts with shared and private thought spaces.
- **Web publishing** — select thoughts to publish as a blog or personal knowledge base.

---

## 15. What this is NOT

- This is not a note-taking app. Notes imply structure, titles, organization. Headlog is a raw dump — unstructured, temporal, no pretense.
- This is not a task manager. The #todo and #reminder tags provide basic task visibility, but this is not Todoist or Asana. The thought comes first; the task is a byproduct.
- This is not a journal app. Traditional journals encourage long-form daily entries. Headlog encourages capturing fragments throughout the day — a sentence here, a sentence there.
- This is not a second brain. Tools like Notion, Obsidian, and Roam organize knowledge into interlinked graphs. Headlog is simpler — a chronological stream of raw thoughts with automatic categorization and AI-powered recall.

---

## 16. Summary

Headlog is a personal thought capture system built around one principle: the distance between having a thought and saving it should be zero.

One text box. Dump what's in your head. Hit save. Behind the scenes, your thought is timestamped, auto-tagged through a 3-layer hybrid system (manual chips + keyword scanner + AI enrichment), stored in dual format (SQLite for speed, Markdown for durability), and made instantly searchable. Three tiers of retrieval intelligence let you recall, search, and reflect on your thoughts — from instant keyword search to full AI-powered analysis via Claude Code.

The entire system is a single Python file with zero dependencies, running on localhost, using SQLite for storage and plain markdown for backup. It starts with your Mac, runs forever in the background, and never needs maintenance. Your data stays local, private, and yours.

It's not a product. It's a personal utility. A raw log of what's in your head. The tool that catches every thought before it disappears.

---

*Document updated: March 23, 2026*
*v1.1 — Added private tags (#private_todo, #private_reminder)*
*Based on design conversation with Claude*
