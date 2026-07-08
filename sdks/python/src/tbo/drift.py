"""Drift detection — alerts when an agent's token consumption trends upward."""

from __future__ import annotations

import logging
import threading
import time
from collections import deque
from typing import Callable

from pydantic import BaseModel, Field

logger = logging.getLogger("tbo.drift")


class DriftAlert(BaseModel):
    """Fired when an agent's token usage drifts above its baseline."""

    agent_id: str
    workspace: str
    baseline_avg: float
    recent_avg: float
    increase_pct: float
    window_size: int
    recent_window: int
    timestamp: float = Field(default_factory=time.time)


class DriftConfig(BaseModel):
    """Configuration for drift detection."""

    # Total number of calls to keep in the rolling window
    window_size: int = Field(default=50, ge=10)
    # How many recent calls to compare against the rest
    recent_window: int = Field(default=10, ge=3)
    # Percentage increase that triggers an alert (0.3 = 30%)
    sensitivity: float = Field(default=0.3, ge=0.05, le=5.0)
    # Minimum calls before drift detection activates
    min_samples: int = Field(default=15, ge=5)
    # Cooldown between alerts for the same agent (seconds)
    cooldown_seconds: float = Field(default=300.0, ge=0.0)

    model_config = {"arbitrary_types_allowed": True}


class DriftDetector:
    """Tracks per-agent token usage and detects upward drift.

    Uses a simple split-window comparison: divide the rolling history into
    "baseline" (older calls) and "recent" (last N calls). If the recent
    average exceeds the baseline average by more than the sensitivity
    threshold, fire an alert.

    Thread-safe. Designed for <1ms overhead per call.
    """

    def __init__(self, config: DriftConfig, on_drift: Callable[[DriftAlert], None] | None = None):
        self._config = config
        self._on_drift = on_drift
        self._lock = threading.Lock()
        # agent_key -> deque of token counts
        self._windows: dict[str, deque[int]] = {}
        # agent_key -> last alert timestamp (for cooldown)
        self._last_alert: dict[str, float] = {}

    def record(self, workspace: str, agent_id: str, total_tokens: int) -> DriftAlert | None:
        """Record a call's token count and check for drift.

        Returns a DriftAlert if drift is detected, None otherwise.
        """
        key = f"{workspace}\x1f{agent_id}"

        with self._lock:
            if key not in self._windows:
                self._windows[key] = deque(maxlen=self._config.window_size)

            window = self._windows[key]
            window.append(total_tokens)

            # Not enough data yet
            if len(window) < self._config.min_samples:
                return None

            # Split into baseline and recent
            recent_size = min(self._config.recent_window, len(window) // 3)
            if recent_size < 3:
                return None

            items = list(window)
            recent = items[-recent_size:]
            baseline = items[:-recent_size]

            if not baseline:
                return None

            baseline_avg = sum(baseline) / len(baseline)
            recent_avg = sum(recent) / len(recent)

            # Avoid division by zero on negligible baselines
            if baseline_avg < 10:
                return None

            increase_pct = (recent_avg - baseline_avg) / baseline_avg

            if increase_pct < self._config.sensitivity:
                return None

            # Cooldown check
            now = time.time()
            last = self._last_alert.get(key, 0.0)
            if now - last < self._config.cooldown_seconds:
                return None

            self._last_alert[key] = now

        alert = DriftAlert(
            agent_id=agent_id,
            workspace=workspace,
            baseline_avg=baseline_avg,
            recent_avg=recent_avg,
            increase_pct=increase_pct * 100,
            window_size=self._config.window_size,
            recent_window=recent_size,
        )

        logger.warning(
            f"Drift detected for '{agent_id}': usage up {alert.increase_pct:.0f}% "
            f"(baseline {baseline_avg:.0f} -> recent {recent_avg:.0f} tokens/call)"
        )

        if self._on_drift:
            self._on_drift(alert)

        return alert

    def get_stats(self, workspace: str, agent_id: str) -> dict | None:
        """Get current stats for an agent (for dashboards/debugging)."""
        key = f"{workspace}\x1f{agent_id}"
        with self._lock:
            window = self._windows.get(key)
            if not window:
                return None

            items = list(window)
            recent_size = min(self._config.recent_window, len(items) // 3)
            recent = items[-recent_size:] if recent_size >= 3 else items
            baseline = items[:-recent_size] if recent_size >= 3 else []

            return {
                "agent_id": agent_id,
                "workspace": workspace,
                "total_calls": len(items),
                "baseline_avg": sum(baseline) / len(baseline) if baseline else 0,
                "recent_avg": sum(recent) / len(recent) if recent else 0,
                "min_tokens": min(items),
                "max_tokens": max(items),
                "overall_avg": sum(items) / len(items),
            }

    def reset(self, workspace: str, agent_id: str) -> None:
        """Reset drift tracking for an agent (e.g., after a known template change)."""
        key = f"{workspace}\x1f{agent_id}"
        with self._lock:
            self._windows.pop(key, None)
            self._last_alert.pop(key, None)
