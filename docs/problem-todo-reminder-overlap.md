# Problem: The Todo-Reminder Overlap

**Date:** March 27, 2026
**Status:** Open problem — no solution proposed yet

---

## The core tension

A single thought can carry both `#todo` and `#reminder` tags. This is not a bug in tagging — it reflects a genuine real-world reality. Many tasks are *both* something you need to do (todo) *and* something attached to a specific time (reminder):

- "Need to submit the tax form by Friday" → `#todo` (from "need to"), `#reminder` (from "by Friday")
- "Reply to Akshat's comments by today" → `#todo` (from "reply to"), `#reminder` (from "by today")
- "Need to call mom about dinner plans this weekend" → `#todo` (from "need to"), `#reminder` (from "this weekend"), `#people` (from "mom")

The keyword scanner correctly identifies both dimensions. The problem is not in the detection — it's in **what the user sees and can do about it**.

---

## The two widgets have different interaction models

### Reminders widget
- Shows thoughts tagged `#reminder`
- Displays timestamp and text
- **No checkbox. No concept of "done."**
- It's a read-only list — you see it, you remember it, that's it

### Todos widget
- Shows thoughts tagged `#todo`
- Displays text with a **checkbox**
- Implies a completion model — you can check it off, it gets a strikethrough
- The checkbox gives a sense of progress and closure

These are fundamentally different UX contracts:
- Reminders say: "here's what's coming up"
- Todos say: "here's what you need to do, and you can mark it done"

---

## What goes wrong for the user

### Scenario 1: Thought appears in both panels

If we don't filter, a thought like "Reply to Akshat's comments by today" shows up in *both* panels simultaneously:

- In **Reminders**: no checkbox, just text
- In **Todos**: checkbox, can mark done

The user sees the same text twice with different interaction affordances. Confusing questions arise:
- "I checked it off in todos — why is it still sitting in my reminders?"
- "Which one is the 'real' one? Do I act on the reminder or the todo?"
- "Did I already handle this? It's checked in one place but staring at me in the other."

### Scenario 2: We filter reminders out of todos (current state)

We currently hide any thought that has `#reminder` from the todos panel. This eliminates duplication, but introduces a *different* problem:

- "Reply to Akshat's comments by today" now **only** appears in Reminders
- But the Reminders widget has **no checkbox**
- The user cannot mark it as done
- It sits in the reminders list indefinitely, even after the user has completed the task
- There is no closure, no way to clear it

This is arguably worse — the user completed a task but has no way to tell the system about it. The reminder becomes stale noise.

### Scenario 3: The "pure reminder" vs "task with a deadline"

Not all reminders are tasks. Some are genuinely just reminders — time-anchored notes with no action to take:

- "Meeting with Raj at 4pm" → you don't "complete" a meeting reminder, you just attend
- "Mom's birthday is next Tuesday" → awareness, not a task
- "Dentist appointment tomorrow at 11" → it happens, you don't check it off

But some reminders ARE tasks:

- "Submit the tax form by Friday" → you need to do this, and you need to know it's done
- "Buy flowers for Mom's birthday by Monday" → action + deadline
- "Reply to the email by end of day" → action + deadline

The current system treats both the same way: read-only text in the reminders panel, no completion tracking. The pure reminders are fine. The deadline-tasks are stranded without a checkbox.

---

## The deeper design question

The product document (§8.7) defines the separation clearly:

> **#todo** — open-ended tasks with no specific time. "Fix the login bug." "Read that book on stoicism."
> **#reminder** — time-bound one-off items. "Meeting today at 4pm." "Dentist tomorrow at 11am."

This is clean in theory, but real human thoughts don't fit neatly into one category. "Submit the report by Friday" is *both* a task and a time-bound item. The tagging system correctly captures both dimensions — but the UI only knows how to present one dimension at a time.

The question isn't "which panel should this thought appear in?" The question is: **what can the user do with a time-bound task, and where do they do it?**

Right now:
- If it shows in Todos → it has a checkbox but loses its time context
- If it shows in Reminders → it has time context but no checkbox
- If it shows in both → it's confusing and redundant

None of these are great.

---

## Summary of the problem

| Situation | What happens | User impact |
|-----------|-------------|-------------|
| Thought has only `#todo` | Shows in Todos with checkbox | Works perfectly |
| Thought has only `#reminder` | Shows in Reminders, no checkbox | Works perfectly for pure reminders |
| Thought has both `#todo` + `#reminder` | Currently: hidden from Todos, shown only in Reminders | User cannot mark a deadline-task as done |
| Thought has both (if unfiltered) | Shows in both panels | Duplicate, confusing, checkbox state doesn't sync |

The fundamental gap: **there is no UI affordance for a task that has a deadline.** The system can detect it (both tags), but neither widget is designed to handle this hybrid.
