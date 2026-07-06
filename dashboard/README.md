# TBO Dashboard

Web interface for visualizing agent budgets, usage, and policy configuration. Connects to the TBO Engine API.

## Stack

- Next.js 15 (App Router)
- Tailwind CSS
- Recharts (charts)
- TypeScript

## Running locally

```bash
cd dashboard
npm install
npm run dev
```

Open http://localhost:3000.

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `TBO_ENGINE_URL` | `http://localhost:8000` | URL of the TBO Engine API |

## Pages

- `/` Landing page
- `/dashboard` Overview with usage chart and agent table
- `/dashboard/agents` Agent budget management
- `/dashboard/policies` Policy configuration
