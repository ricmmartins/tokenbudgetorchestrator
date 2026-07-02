"""Redis-backed atomic budget store for multi-process budget enforcement."""

from __future__ import annotations

import logging
import time
from typing import Optional

import redis

logger = logging.getLogger("tbo.engine.budget_store")

# Period durations in seconds (used as Redis key TTL)
PERIOD_TTL = {
    "hourly": 3600,
    "daily": 86400,
    "weekly": 604800,
    "monthly": 2592000,
}


class RedisBudgetStore:
    """Atomic budget tracking using Redis.

    Uses Redis INCRBY for race-condition-free budget counting across
    multiple SDK instances and processes.

    Key schema:
        tbo:budget:{workspace}:{agent_id}:tokens  → current token usage (int)
        tbo:budget:{workspace}:{agent_id}:cost    → current cost in microdollars (int, $1 = 1_000_000)
        tbo:budget:{workspace}:{agent_id}:config  → budget config (hash)
    """

    def __init__(self, redis_url: str = "redis://localhost:6379/0"):
        self._redis = redis.from_url(redis_url, decode_responses=True)

    def _key(self, workspace: str, agent_id: str, suffix: str) -> str:
        return f"tbo:budget:{workspace}:{agent_id}:{suffix}"

    def configure_budget(
        self,
        workspace: str,
        agent_id: str,
        max_tokens: Optional[int] = None,
        max_cost_usd: Optional[float] = None,
        period: str = "daily",
        on_exceed: str = "block",
        fallback_model: Optional[str] = None,
        warning_threshold: float = 0.8,
    ) -> dict:
        """Store budget configuration for an agent."""
        config_key = self._key(workspace, agent_id, "config")
        config = {
            "max_tokens": str(max_tokens or 0),
            "max_cost_micros": str(int((max_cost_usd or 0) * 1_000_000)),
            "period": period,
            "on_exceed": on_exceed,
            "fallback_model": fallback_model or "",
            "warning_threshold": str(warning_threshold),
        }
        self._redis.hset(config_key, mapping=config)
        return config

    def check_and_increment(
        self,
        workspace: str,
        agent_id: str,
        tokens: int,
        cost_micros: int,
    ) -> dict:
        """Atomically check budget and increment usage.

        Uses a Lua script for atomic check-and-increment to prevent
        race conditions between multiple processes.

        Returns:
            dict with keys: allowed, used_tokens, used_cost_micros,
            max_tokens, max_cost_micros, fallback_model, status
        """
        token_key = self._key(workspace, agent_id, "tokens")
        cost_key = self._key(workspace, agent_id, "cost")
        config_key = self._key(workspace, agent_id, "config")

        # Lua script: atomic check + increment
        lua_script = """
        local token_key = KEYS[1]
        local cost_key = KEYS[2]
        local config_key = KEYS[3]
        local add_tokens = tonumber(ARGV[1])
        local add_cost = tonumber(ARGV[2])
        local period_ttl = tonumber(ARGV[3])

        -- Get config
        local max_tokens = tonumber(redis.call('HGET', config_key, 'max_tokens') or '0')
        local max_cost = tonumber(redis.call('HGET', config_key, 'max_cost_micros') or '0')
        local on_exceed = redis.call('HGET', config_key, 'on_exceed') or 'block'
        local fallback = redis.call('HGET', config_key, 'fallback_model') or ''

        -- Get current usage
        local current_tokens = tonumber(redis.call('GET', token_key) or '0')
        local current_cost = tonumber(redis.call('GET', cost_key) or '0')

        -- Check if exceeded
        local exceeded = false
        if max_tokens > 0 and (current_tokens + add_tokens) > max_tokens then
            exceeded = true
        end
        if max_cost > 0 and (current_cost + add_cost) > max_cost then
            exceeded = true
        end

        if exceeded then
            if on_exceed == 'block' then
                return {'blocked', tostring(current_tokens), tostring(current_cost),
                        tostring(max_tokens), tostring(max_cost), fallback}
            elseif on_exceed == 'fallback' then
                -- Still increment (fallback model will be used)
                redis.call('INCRBY', token_key, add_tokens)
                redis.call('INCRBY', cost_key, add_cost)
                if redis.call('TTL', token_key) == -1 then
                    redis.call('EXPIRE', token_key, period_ttl)
                    redis.call('EXPIRE', cost_key, period_ttl)
                end
                return {'fallback', tostring(current_tokens + add_tokens),
                        tostring(current_cost + add_cost),
                        tostring(max_tokens), tostring(max_cost), fallback}
            else
                -- alert: increment but flag
                redis.call('INCRBY', token_key, add_tokens)
                redis.call('INCRBY', cost_key, add_cost)
                if redis.call('TTL', token_key) == -1 then
                    redis.call('EXPIRE', token_key, period_ttl)
                    redis.call('EXPIRE', cost_key, period_ttl)
                end
                return {'alert', tostring(current_tokens + add_tokens),
                        tostring(current_cost + add_cost),
                        tostring(max_tokens), tostring(max_cost), fallback}
            end
        end

        -- Not exceeded: increment
        redis.call('INCRBY', token_key, add_tokens)
        redis.call('INCRBY', cost_key, add_cost)

        -- Set TTL for automatic period reset
        if redis.call('TTL', token_key) == -1 then
            redis.call('EXPIRE', token_key, period_ttl)
            redis.call('EXPIRE', cost_key, period_ttl)
        end

        return {'ok', tostring(current_tokens + add_tokens),
                tostring(current_cost + add_cost),
                tostring(max_tokens), tostring(max_cost), fallback}
        """

        config = self._redis.hgetall(config_key)
        period = config.get("period", "daily")
        ttl = PERIOD_TTL.get(period, 86400)

        result = self._redis.eval(
            lua_script,
            3,
            token_key,
            cost_key,
            config_key,
            tokens,
            cost_micros,
            ttl,
        )

        status, used_tokens, used_cost, max_tokens, max_cost, fallback = result

        return {
            "status": status,
            "allowed": status != "blocked",
            "used_tokens": int(used_tokens),
            "used_cost_micros": int(used_cost),
            "max_tokens": int(max_tokens),
            "max_cost_micros": int(max_cost),
            "fallback_model": fallback or None,
        }

    def get_usage(self, workspace: str, agent_id: str) -> dict:
        """Get current usage for an agent."""
        token_key = self._key(workspace, agent_id, "tokens")
        cost_key = self._key(workspace, agent_id, "cost")
        config_key = self._key(workspace, agent_id, "config")

        tokens = int(self._redis.get(token_key) or 0)
        cost_micros = int(self._redis.get(cost_key) or 0)
        config = self._redis.hgetall(config_key)
        ttl = self._redis.ttl(token_key)

        return {
            "workspace": workspace,
            "agent_id": agent_id,
            "used_tokens": tokens,
            "used_cost_usd": cost_micros / 1_000_000,
            "max_tokens": int(config.get("max_tokens", 0)),
            "max_cost_usd": int(config.get("max_cost_micros", 0)) / 1_000_000,
            "period": config.get("period", "daily"),
            "period_resets_in_seconds": max(ttl, 0),
            "on_exceed": config.get("on_exceed", "block"),
        }

    def reset_budget(self, workspace: str, agent_id: str) -> None:
        """Manually reset an agent's usage counters."""
        token_key = self._key(workspace, agent_id, "tokens")
        cost_key = self._key(workspace, agent_id, "cost")
        self._redis.delete(token_key, cost_key)

    def list_agents(self, workspace: str) -> list[str]:
        """List all agents with configured budgets in a workspace."""
        pattern = f"tbo:budget:{workspace}:*:config"
        keys = self._redis.keys(pattern)
        agents = []
        for key in keys:
            # Extract agent_id from key
            parts = key.split(":")
            if len(parts) >= 4:
                agents.append(parts[3])
        return agents
