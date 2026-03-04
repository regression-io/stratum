# Breadcrumb Intent Tracking

Before each logical batch of file edits, write a one-line intent breadcrumb:

```bash
echo "$(date -Iseconds) | <intent>" >> .forge/breadcrumbs.log
```

## Rules

- **One breadcrumb per intent, not per file.** Three edits that all serve "theme toggle" get one breadcrumb.
- **Capture WHY, not WHAT.** "Adding theme toggle to header" not "Editing App.jsx and index.css".
- **Write it BEFORE the edits.** If you die mid-batch, the breadcrumb survives.
- **Keep it short.** One line, plain language, no formatting.
- **New intent = new breadcrumb.** If you shift from "theme toggle" to "fixing a bug you noticed," that's a new breadcrumb.

## Why this exists

This is Forge's granular tracking applied to its own development. The breadcrumb trail lets the next agent (or human) reconstruct what was happening if the session dies. The files on disk show WHAT changed; the breadcrumbs show WHY.
