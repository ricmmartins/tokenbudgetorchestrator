"""TBO Engine — FastAPI application."""

from __future__ import annotations

import os
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(
    title="Token Budget Orchestrator Engine",
    description="Policy engine and telemetry aggregation for multi-agent LLM budget governance",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # TODO: restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_budget_store():
    """Lazy-init Redis budget store."""
    from engine.budget_store import RedisBudgetStore

    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    return RedisBudgetStore(redis_url)


# --- Models ---


class BudgetConfigRequest(BaseModel):
    max_tokens: Optional[int] = None
    max_cost_usd: Optional[float] = None
    period: str = "daily"
    on_exceed: str = "block"
    fallback_model: Optional[str] = None
    warning_threshold: float = 0.8


class BudgetCheckRequest(BaseModel):
    tokens: int
    cost_usd: float = 0.0


# --- Endpoints ---


@app.get("/health")
async def health():
    return {"status": "ok", "version": "0.1.0"}


@app.post("/v1/telemetry/ingest")
async def ingest_telemetry(records: list[dict]):
    """Receive telemetry from SDKs. Metadata only — never prompt content."""
    # TODO: persist to PostgreSQL for historical queries
    return {"accepted": len(records)}


@app.post("/v1/workspaces/{workspace}/agents/{agent_id}/budget")
async def configure_budget(workspace: str, agent_id: str, config: BudgetConfigRequest):
    """Configure budget for an agent."""
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
async def check_budget(workspace: str, agent_id: str, request: BudgetCheckRequest):
    """Atomically check and record usage against budget."""
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
async def get_agent_usage(workspace: str, agent_id: str):
    """Get current usage for an agent."""
    store = get_budget_store()
    return store.get_usage(workspace, agent_id)


@app.get("/v1/workspaces/{workspace}/agents")
async def list_agents(workspace: str):
    """List all agents with budgets in a workspace."""
    store = get_budget_store()
    agents = store.list_agents(workspace)
    return {"workspace": workspace, "agents": agents}


@app.post("/v1/workspaces/{workspace}/agents/{agent_id}/reset")
async def reset_budget(workspace: str, agent_id: str):
    """Manually reset an agent's budget counters."""
    store = get_budget_store()
    store.reset_budget(workspace, agent_id)
    return {"status": "reset", "agent_id": agent_id}


@app.post("/v1/workspaces/{workspace}/policies")
async def create_policy(workspace: str, policy: dict):
    """Create or update a policy for a workspace."""
    # TODO: store policy in PostgreSQL, push to connected SDKs
    return {"status": "created", "policy": policy}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
