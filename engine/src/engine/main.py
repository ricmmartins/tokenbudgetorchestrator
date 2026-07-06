"""TBO Engine — FastAPI application."""

from __future__ import annotations

import os
import re
from typing import Annotated, Optional

from fastapi import Depends, FastAPI, HTTPException, Security
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, Field

app = FastAPI(
    title="Token Budget Orchestrator Engine",
    description="Policy engine and telemetry aggregation for multi-agent LLM budget governance",
    version="0.1.0",
)

# CORS: restrict origins in production via TBO_CORS_ORIGINS env var
_cors_origins = os.getenv("TBO_CORS_ORIGINS", "http://localhost:3000").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type"],
)

# --- Authentication ---

_api_key_header = APIKeyHeader(name="X-TBO-API-Key", auto_error=False)


async def require_api_key(api_key: str = Security(_api_key_header)):
    """Validate API key from request header."""
    expected_key = os.getenv("TBO_API_KEY")
    if not expected_key:
        # No key configured = open access (dev mode)
        return None
    if not api_key or api_key != expected_key:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
    return api_key


# --- Input validation ---

_IDENTIFIER_PATTERN = re.compile(r"^[a-zA-Z0-9_\-\.]+$")


def validate_identifier(value: str, name: str) -> str:
    """Validate workspace/agent_id to prevent key injection."""
    if not value or not _IDENTIFIER_PATTERN.match(value):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid {name}: must match [a-zA-Z0-9_\\-\\.]+",
        )
    if len(value) > 128:
        raise HTTPException(status_code=400, detail=f"{name} too long (max 128 chars)")
    return value


def get_budget_store():
    """Lazy-init Redis budget store."""
    from engine.budget_store import RedisBudgetStore

    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    return RedisBudgetStore(redis_url)


# --- Models ---


class BudgetConfigRequest(BaseModel):
    max_tokens: Optional[int] = Field(default=None, ge=0)
    max_cost_usd: Optional[float] = Field(default=None, ge=0.0)
    period: str = "daily"
    on_exceed: str = "block"
    fallback_model: Optional[str] = None
    warning_threshold: float = Field(default=0.8, ge=0.0, le=1.0)


class BudgetCheckRequest(BaseModel):
    tokens: int = Field(gt=0)
    cost_usd: float = Field(default=0.0, ge=0.0)


# --- Endpoints ---


@app.get("/health")
async def health():
    return {"status": "ok", "version": "0.1.0"}


@app.post("/v1/telemetry/ingest")
async def ingest_telemetry(records: list[dict], _key=Depends(require_api_key)):
    """Receive telemetry from SDKs. Metadata only — never prompt content."""
    if len(records) > 1000:
        raise HTTPException(status_code=400, detail="Max 1000 records per batch")
    # Storage: PostgreSQL persistence planned for v0.2
    return {"accepted": len(records)}


@app.post("/v1/workspaces/{workspace}/agents/{agent_id}/budget")
async def configure_budget(workspace: str, agent_id: str, config: BudgetConfigRequest, _key=Depends(require_api_key)):
    """Configure budget for an agent."""
    validate_identifier(workspace, "workspace")
    validate_identifier(agent_id, "agent_id")
    store = get_budget_store()
    result = store.configure_budget(
        workspace=workspace,
        agent_id=agent_id,
        max_tokens=config.max_tokens,
        max_cost_usd=config.max_cost_usd,
        period=config.period,
        on_exceed=config.on_exceed,
        fallback_model=config.fallback_model,
        warning_threshold=config.warning_threshold,
    )
    return {"status": "configured", "agent_id": agent_id, "config": result}


@app.post("/v1/workspaces/{workspace}/agents/{agent_id}/check")
async def check_budget(workspace: str, agent_id: str, request: BudgetCheckRequest, _key=Depends(require_api_key)):
    """Atomically check and record usage against budget."""
    validate_identifier(workspace, "workspace")
    validate_identifier(agent_id, "agent_id")
    store = get_budget_store()
    cost_micros = int(request.cost_usd * 1_000_000)
    result = store.check_and_increment(
        workspace=workspace,
        agent_id=agent_id,
        tokens=request.tokens,
        cost_micros=cost_micros,
    )
    return result


@app.get("/v1/workspaces/{workspace}/agents/{agent_id}/usage")
async def get_agent_usage(workspace: str, agent_id: str, _key=Depends(require_api_key)):
    """Get current usage for an agent."""
    validate_identifier(workspace, "workspace")
    validate_identifier(agent_id, "agent_id")
    store = get_budget_store()
    return store.get_usage(workspace, agent_id)


@app.get("/v1/workspaces/{workspace}/agents")
async def list_agents(workspace: str, _key=Depends(require_api_key)):
    """List all agents with budgets in a workspace."""
    validate_identifier(workspace, "workspace")
    store = get_budget_store()
    agents = store.list_agents(workspace)
    return {"workspace": workspace, "agents": agents}


@app.post("/v1/workspaces/{workspace}/agents/{agent_id}/reset")
async def reset_budget(workspace: str, agent_id: str, _key=Depends(require_api_key)):
    """Manually reset an agent's budget counters."""
    validate_identifier(workspace, "workspace")
    validate_identifier(agent_id, "agent_id")
    store = get_budget_store()
    store.reset_budget(workspace, agent_id)
    return {"status": "reset", "agent_id": agent_id}


@app.post("/v1/workspaces/{workspace}/policies")
async def create_policy(workspace: str, policy: dict, _key=Depends(require_api_key)):
    """Create or update a policy for a workspace."""
    validate_identifier(workspace, "workspace")
    # Storage: policy persistence planned for v0.2
    return {"status": "created", "policy": policy}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
