# TBO Engine

Optional backend for multi-process budget coordination. If you only run a single process, the SDK handles everything locally and you do not need this.

## What it does

- Atomic budget enforcement across multiple SDK instances using Redis + Lua scripts
- REST API for budget configuration, usage queries, and policy management
- Telemetry ingestion endpoint (receives metadata only, never prompt content)

## Running locally

```bash
# Start Redis
docker run -d -p 6379:6379 redis:7-alpine

# Run the engine
cd engine
pip install -e .
uvicorn engine.main:app --reload --port 8000
```

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `REDIS_URL` | `redis://localhost:6379/0` | Redis connection string |
| `TBO_API_KEY` | (none) | API key for authentication. If unset, all requests are allowed (dev mode). |
| `TBO_CORS_ORIGINS` | `http://localhost:3000` | Comma-separated allowed origins |

## API

All endpoints (except `/health`) require the `X-TBO-API-Key` header when `TBO_API_KEY` is set.

```
GET  /health
POST /v1/telemetry/ingest
POST /v1/workspaces/{ws}/agents/{id}/budget    (configure)
POST /v1/workspaces/{ws}/agents/{id}/check     (atomic check + increment)
GET  /v1/workspaces/{ws}/agents/{id}/usage
GET  /v1/workspaces/{ws}/agents
POST /v1/workspaces/{ws}/agents/{id}/reset
POST /v1/workspaces/{ws}/policies
```

## Docker

```bash
docker build -t tbo-engine .
docker run -p 8000:8000 -e REDIS_URL=redis://host:6379/0 -e TBO_API_KEY=your-secret tbo-engine
```
