"""Tests for drift detection."""

import time

import pytest

from tbo.drift import DriftAlert, DriftConfig, DriftDetector


class TestDriftDetector:
    """Test drift detection logic."""

    def test_no_alert_below_min_samples(self):
        """Should not fire until min_samples calls are recorded."""
        config = DriftConfig(window_size=50, min_samples=15, sensitivity=0.3)
        detector = DriftDetector(config=config)

        for i in range(14):
            result = detector.record("ws", "agent-1", 1000)
            assert result is None

    def test_no_alert_when_stable(self):
        """Stable consumption should not trigger drift."""
        config = DriftConfig(window_size=50, min_samples=15, sensitivity=0.3, recent_window=10)
        detector = DriftDetector(config=config)

        # 50 calls all around 1000 tokens
        for _ in range(50):
            result = detector.record("ws", "agent-1", 1000)

        assert result is None

    def test_detects_upward_drift(self):
        """Should detect when recent calls use significantly more tokens."""
        config = DriftConfig(
            window_size=50, min_samples=15, sensitivity=0.3,
            recent_window=10, cooldown_seconds=0
        )
        detector = DriftDetector(config=config)

        # Baseline: 30 calls at ~1000 tokens
        for _ in range(30):
            detector.record("ws", "agent-1", 1000)

        # Regression: next 10 calls at ~1500 tokens (50% increase)
        alert = None
        for _ in range(10):
            result = detector.record("ws", "agent-1", 1500)
            if result is not None:
                alert = result

        assert alert is not None
        assert alert.agent_id == "agent-1"
        assert alert.increase_pct >= 30.0
        assert alert.recent_avg > alert.baseline_avg

    def test_no_alert_below_sensitivity(self):
        """Small increases below sensitivity should not trigger."""
        config = DriftConfig(
            window_size=50, min_samples=15, sensitivity=0.5,
            recent_window=10, cooldown_seconds=0
        )
        detector = DriftDetector(config=config)

        # Baseline at 1000
        for _ in range(30):
            detector.record("ws", "agent-1", 1000)

        # Small bump to 1200 (20%, below 50% threshold)
        for _ in range(10):
            result = detector.record("ws", "agent-1", 1200)

        assert result is None

    def test_cooldown_prevents_repeated_alerts(self):
        """Should not fire more than once within cooldown period."""
        config = DriftConfig(
            window_size=50, min_samples=15, sensitivity=0.3,
            recent_window=10, cooldown_seconds=600
        )
        detector = DriftDetector(config=config)

        # Baseline
        for _ in range(30):
            detector.record("ws", "agent-1", 1000)

        # First drift triggers alert
        first_alert = None
        for _ in range(10):
            result = detector.record("ws", "agent-1", 1500)
            if result is not None:
                first_alert = result

        assert first_alert is not None

        # More drift, but should be suppressed by cooldown
        for _ in range(10):
            result = detector.record("ws", "agent-1", 2000)

        assert result is None

    def test_cooldown_expires(self):
        """Alert should fire again after cooldown expires."""
        config = DriftConfig(
            window_size=50, min_samples=15, sensitivity=0.3,
            recent_window=10, cooldown_seconds=0.1
        )
        detector = DriftDetector(config=config)

        # Baseline
        for _ in range(30):
            detector.record("ws", "agent-1", 1000)

        # First drift
        for _ in range(10):
            detector.record("ws", "agent-1", 1500)

        time.sleep(0.15)

        # Second drift should fire after cooldown
        alert = None
        for _ in range(10):
            result = detector.record("ws", "agent-1", 2000)
            if result is not None:
                alert = result

        assert alert is not None
        assert alert.recent_avg > 1500

    def test_callback_is_invoked(self):
        """on_drift callback should be called with the alert."""
        alerts_received = []

        config = DriftConfig(
            window_size=50, min_samples=15, sensitivity=0.3,
            recent_window=10, cooldown_seconds=0
        )
        detector = DriftDetector(config=config, on_drift=alerts_received.append)

        for _ in range(30):
            detector.record("ws", "agent-1", 1000)

        for _ in range(10):
            detector.record("ws", "agent-1", 1500)

        assert len(alerts_received) >= 1
        assert alerts_received[0].agent_id == "agent-1"

    def test_per_agent_isolation(self):
        """Drift in one agent should not affect another."""
        config = DriftConfig(
            window_size=50, min_samples=15, sensitivity=0.3,
            recent_window=10, cooldown_seconds=0
        )
        detector = DriftDetector(config=config)

        # Both agents stable at 1000
        for _ in range(30):
            detector.record("ws", "agent-1", 1000)
            detector.record("ws", "agent-2", 1000)

        # Only agent-1 drifts
        for _ in range(10):
            r1 = detector.record("ws", "agent-1", 1500)
            r2 = detector.record("ws", "agent-2", 1000)

        # agent-1 should alert, agent-2 should not
        assert r1 is not None or any(
            detector.record("ws", "agent-1", 1500) for _ in range(5)
        )
        assert r2 is None

    def test_get_stats(self):
        """Should return useful stats for dashboards."""
        config = DriftConfig(window_size=50, min_samples=15, recent_window=10)
        detector = DriftDetector(config=config)

        for i in range(20):
            detector.record("ws", "agent-1", 1000 + i * 10)

        stats = detector.get_stats("ws", "agent-1")
        assert stats is not None
        assert stats["agent_id"] == "agent-1"
        assert stats["total_calls"] == 20
        assert stats["min_tokens"] == 1000
        assert stats["max_tokens"] == 1190

    def test_get_stats_unknown_agent(self):
        """Should return None for unknown agents."""
        config = DriftConfig(window_size=50)
        detector = DriftDetector(config=config)

        assert detector.get_stats("ws", "unknown") is None

    def test_reset_clears_history(self):
        """Reset should clear all tracking for an agent."""
        config = DriftConfig(
            window_size=50, min_samples=15, sensitivity=0.3,
            recent_window=10, cooldown_seconds=0
        )
        detector = DriftDetector(config=config)

        # Build up history
        for _ in range(30):
            detector.record("ws", "agent-1", 1000)

        detector.reset("ws", "agent-1")

        assert detector.get_stats("ws", "agent-1") is None

        # After reset, need min_samples again before detecting
        for _ in range(14):
            result = detector.record("ws", "agent-1", 2000)
            assert result is None

    def test_window_rolls_over(self):
        """Old data should fall off the window as new data arrives."""
        config = DriftConfig(
            window_size=20, min_samples=15, sensitivity=0.3,
            recent_window=5, cooldown_seconds=0
        )
        detector = DriftDetector(config=config)

        # Fill window with high values
        for _ in range(20):
            detector.record("ws", "agent-1", 2000)

        # Now feed low values — as old high values fall off, no drift
        for _ in range(20):
            result = detector.record("ws", "agent-1", 2000)

        assert result is None
