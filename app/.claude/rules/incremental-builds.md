# Incremental Builds: Never Break the App Mid-Build

When building or rebuilding UI components, the app must remain functional at every step.

## Rules

1. **Never delete a working component before its replacement is wired in.** Old and new can coexist. Delete old files only after the new ones are rendering correctly.

2. **Never rewrite CSS wholesale.** Add new token layers alongside existing ones. Remove old tokens only after confirming no component references them.

3. **Build new components in isolation first.** Create the new file, import it conditionally or behind a flag, verify it renders, then swap it into the tree.

4. **One swap at a time.** Replace one component per commit-worthy checkpoint. If VisionSurface imports 5 children, replace them one at a time, verifying after each.

5. **Verify after every structural change.** After any change that affects imports, routing, or layout — confirm the app loads and the terminal still works. Use `npm run build` as a smoke test at minimum.

6. **Keep the old path available.** If replacing a view system, keep the old views importable until the new ones are proven. Feature flags or simple boolean state are fine.

7. **CSS additions before CSS deletions.** Add new classes/tokens first. Migrate components to use them. Only then remove the old ones.

## Why

The developer's terminal session runs inside this app. Breaking the app kills the terminal. Killing the terminal kills the agent. A build that breaks the app is a build that stops itself.
