# stratum-nextjs-example

Embed Stratum pipeline monitoring into a Next.js app using `@stratum/ui`.

## Setup

```bash
npm install
npm run dev
```

Requires `stratum-mcp serve` running on port 7821:
```bash
stratum-mcp serve
```

## What it shows

- `<GateQueue>` — approve/reject pending pipeline gates
- `<RunList>` — browse pipeline run history

## Components used

```jsx
import { RunList, GateQueue } from '@stratum/ui'
```

## API proxy (optional)

`pages/api/proxy/[...path].js` forwards requests to stratum-mcp serve.
Useful when serving from a different port. Set `apiBase="/api/proxy"` on components.
