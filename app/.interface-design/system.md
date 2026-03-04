# Compose Design System

## Intent
Compose is an agentic IDE — a place where anyone, from vibe coders to senior engineers, shapes software through conversation with AI. Newbie-friendly by default, expert-powerful on demand.

**Feel:** A warm workshop. Capable and inviting. Power without intimidation. Like sitting next to a skilled collaborator who makes you feel like you belong.

## Direction
Warm dark. Not cold developer-dark, not friendly-light. The warmth comes from amber undertones in surfaces and the glow of activity. The darkness provides focus without being foreboding.

## Signature
The conversational surface. Not a terminal — a place where you talk and things happen. Expert mode reveals the raw terminal underneath. Same power, two faces.

## Palette

### Surfaces (warm carbon, increasing elevation = warmer)
- `--compose-void`: #0a0a10 — deepest background, the space behind everything
- `--compose-base`: #0f0e14 — primary canvas
- `--compose-raised`: #16141e — cards, panels, one step up
- `--compose-overlay`: #1e1b28 — dropdowns, modals, floating
- `--compose-inset`: #0c0b11 — inputs, wells, recessed surfaces

### Text (warm cream hierarchy)
- `--ink-primary`: #ede9e0 — default text, warm not white
- `--ink-secondary`: #a8a295 — supporting text
- `--ink-tertiary`: #6d6860 — metadata, timestamps
- `--ink-muted`: #4a4640 — disabled, placeholder

### Borders (warm, barely there)
- `--border-standard`: rgba(237, 233, 224, 0.06)
- `--border-soft`: rgba(237, 233, 224, 0.04)
- `--border-emphasis`: rgba(237, 233, 224, 0.10)
- `--border-focus`: rgba(199, 146, 70, 0.40)

### Brand / Accent (ember + indigo)
- `--ember`: #c79246 — primary accent, warmth, activity, CTA
- `--ember-glow`: rgba(199, 146, 70, 0.15) — hover states, highlights
- `--indigo`: #7c6fbd — secondary accent, links, guidance
- `--indigo-glow`: rgba(124, 111, 189, 0.15)

### Semantic
- `--success`: #6da87a — muted sage green
- `--warning`: #c7924680 — ember at half, caution
- `--error`: #b85c5c — muted warm red
- `--info`: #7c6fbd — indigo

## Typography
- **Primary:** Inter — approachable, readable, professional without being cold
- **Mono:** 'Berkeley Mono', 'JetBrains Mono', 'Menlo', monospace — for terminal/code, warm monospace
- **Scale:** 13px base, 1.5 line height for comfort
- **Headings:** semibold, -0.02em tracking, warm not sharp
- **Labels:** medium weight, 11px, uppercase tracking 0.05em

## Spacing
- Base: 4px
- Micro: 4px (icon gaps)
- Component: 8px, 12px (within buttons, cards)
- Section: 16px, 24px (between groups)
- Major: 32px, 48px (between distinct areas)

## Depth Strategy
Borders only. No shadows. Warm rgba borders at low opacity. Surfaces differentiate through color shift, not shadow. This keeps the compose feel — solid, grounded, not floating.

## Border Radius
- Small: 6px (inputs, buttons)
- Medium: 8px (cards, panels)
- Large: 12px (modals)
Slightly rounded — approachable but not bubbly.

## Terminal Treatment
The terminal is the primary surface but should not intimidate:
- Same warm dark background as the app (not a jarring black box)
- Warm text colors matching the palette (cream, not green-on-black)
- Comfortable font size and line height
- The terminal border/container should feel like part of the app, not an embedded foreign object
