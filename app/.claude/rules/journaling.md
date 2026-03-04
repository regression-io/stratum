# Journaling Rule

Forge's developer journal (`docs/journal/`) tells the story of how Forge was built from beginning to end. Every session contributes a chapter.

## When to journal

After every session that produces code changes, doc updates, or significant decisions — before the session ends:

1. **Write or update a journal entry** in `docs/journal/YYYY-MM-DD-session-N-<slug>.md`
2. **Update the journal index** in `docs/journal/README.md` with the new entry

## What goes in an entry

Follow the established format (see existing entries for reference):

- **What happened** — Narrative of the session. What was the human's ask? What did we discover? What broke? What was the fix? Tell the story, don't just list changes.
- **What we built** — File manifest: new and modified files with brief descriptions.
- **What we learned** — Numbered insights. Not just "what" but "why it matters." These are the reusable lessons.
- **Open threads** — Checkbox list of unfinished work, unanswered questions, things to test.

## Voice and tone

- First person plural ("we") — the human and the agent building together
- Honest about failures and wrong turns — the journal captures the real process, not the idealized version
- Technical but readable — someone unfamiliar with the codebase should follow the narrative
- The closing line of each entry should be a one-liner that captures the session's character

## Session numbering

Sessions are numbered sequentially (0, 1, 2, 3...) within a date. If multiple entries happen on the same date, increment the session number. Check existing entries in `docs/journal/` before numbering.

## Why this matters

This journal is both the story of Forge and a test case for what Forge will automate. Every entry is raw material for conversation distillation (Phase 3.2). Write entries that a future version of Forge could learn to generate from session transcripts.
