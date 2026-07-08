# Changelog

## [0.2.0] — 2026-07-08

### Added
- **Drift detection**: Proactive alerting when an agent's token consumption trends upward before hitting the budget wall
  - `DriftConfig`: configure window size, sensitivity threshold, cooldown between alerts
  - `DriftDetector`: split-window comparison (recent avg vs. baseline avg) with <1ms overhead per call
  - `DriftAlert`: structured alert with percentage increase, averages, and timestamps
  - `on_drift` callback on `TBOClient` for real-time notifications
  - `get_stats()` for programmatic access to per-agent consumption stats
  - `reset()` to clear tracking after intentional changes (e.g., prompt template deploys)
- Example: `05_drift_detection.py`

## [0.1.0] — 2026-07-02

### Added
- **Python SDK**: TBOClient wrapper for Anthropic/OpenAI with transparent budget governance
- **Node.js SDK**: Full TypeScript port with Zod validation
- **Budget enforcement**: Per-agent token/cost limits with configurable periods (hourly/daily/weekly/monthly)
- **Policy engine**: Rule-based model routing by metadata conditions (task_type, priority, etc.)
- **Fallback mode**: Auto-downgrade to cheaper model when budget exceeded (`on_exceed="fallback"`)
- **Alert mode**: Allow calls but log warnings when budget exceeded (`on_exceed="alert"`)
- **Async telemetry**: Non-blocking metadata collection (never sends prompt content)
- **Local token counting**: Estimate tokens without sending content externally
- **Engine API**: FastAPI backend with Redis atomic budget counters (Lua scripts for race-condition safety)
- **Dashboard**: Next.js app with real-time consumption overview, agent table, and policy management
- **CI pipeline**: GitHub Actions testing Python 3.10-3.12, Node 18-22, and Docker build
- **Examples**: 4 runnable demos (basic usage, policy routing, budget fallback, multi-agent)
- **Docker Compose**: Full local stack (engine + Redis + PostgreSQL)
