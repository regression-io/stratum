---
name: require-breadcrumb-intent
enabled: true
event: file
action: warn
conditions:
  - field: file_path
    operator: not_contains
    pattern: breadcrumbs
---

**Breadcrumb check.** Before this batch of edits, did you write a one-line intent breadcrumb?

```bash
echo "$(date -Iseconds) | <WHY you are making these changes>" >> .forge/breadcrumbs.log
```

The breadcrumb captures intent, not files. Good: "Adding theme toggle to header". Bad: "Editing App.jsx".

If you already wrote one for this batch, carry on.
