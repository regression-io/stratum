# Self-Preservation: Don't Kill Your Own Session

You are running inside Forge's embedded terminal. Your PTY process is a child of the Forge server. If the server restarts, you die. Act accordingly.

## Never do these things

- **Never register a service worker.** It caches broken state and survives server restarts, breaking all page loads.
- **Never modify `package.json` scripts** without warning the human — changes to dev scripts can kill the process tree.
- **Never run `kill`, `pkill`, or signal commands** targeting node, vite, or supervisor processes.
- **Never modify `vite.config.js`** — Vite restarts on config changes, which can cascade.

## Server files: edit carefully

Files in `server/` (index.js, terminal.js, file-watcher.js, supervisor.js) are **hot** — the server doesn't auto-restart on file changes, but if your edits introduce a crash, the supervisor will restart and kill your PTY session.

When editing server files:
1. Make small, isolated changes
2. Validate syntax before saving (`node --check server/file.js`)
3. If the human asks you to restart the server, you may do so
4. Otherwise, tell the human: "I edited server files — restart the server when ready"

## Client files: safer but still careful

Files in `src/` trigger Vite HMR. The singleton terminal pattern survives component re-renders. But:
- Edits to `Terminal.jsx` that expect new server behavior will break until the server is restarted
- Edits that break JSX syntax will crash the page
- Large structural changes to `App.jsx` can cause full page reloads

## If you need to test server changes

If the human explicitly asks you to restart the server, do it. Otherwise, ask first — restarting the server kills your PTY session.

## The golden rule

Before editing any infrastructure file, ask: "If this edit breaks, do I survive?" If the answer is no, tell the human what you want to change and let them decide when to apply it.
