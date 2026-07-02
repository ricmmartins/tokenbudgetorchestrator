"""Async telemetry — sends only metadata to TBO engine. NEVER sends prompt content."""

from __future__ import annotations

import asyncio
import logging
import queue
import threading
from typing import Optional

from tbo.models import UsageRecord

logger = logging.getLogger("tbo.telemetry")


class TelemetryCollector:
    """Collects and batches usage records for async delivery.

    Design principles:
    - NEVER blocks the LLM call path
    - NEVER sends prompt/response content
    - Batches records and sends asynchronously
    - Gracefully degrades if engine is unreachable
    """

    def __init__(
        self,
        engine_url: Optional[str] = None,
        batch_size: int = 10,
        flush_interval_seconds: float = 5.0,
        enabled: bool = True,
    ):
        self._engine_url = engine_url
        self._batch_size = batch_size
        self._flush_interval = flush_interval_seconds
        self._enabled = enabled
        self._queue: queue.Queue[UsageRecord] = queue.Queue(maxsize=10000)
        self._buffer: list[UsageRecord] = []
        self._worker: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

        if self._enabled and self._engine_url:
            self._start_worker()

    def record(self, usage: UsageRecord) -> None:
        """Queue a usage record for async delivery. Never blocks."""
        if not self._enabled:
            return
        try:
            self._queue.put_nowait(usage)
        except queue.Full:
            logger.warning("Telemetry queue full — dropping oldest record")
            try:
                self._queue.get_nowait()
                self._queue.put_nowait(usage)
            except queue.Empty:
                pass

    def _start_worker(self) -> None:
        """Start background thread for batching and sending telemetry."""
        self._worker = threading.Thread(target=self._worker_loop, daemon=True)
        self._worker.start()

    def _worker_loop(self) -> None:
        """Background loop: drain queue, batch, and send."""
        while not self._stop_event.is_set():
            try:
                record = self._queue.get(timeout=self._flush_interval)
                self._buffer.append(record)

                # Drain remaining items up to batch size
                while len(self._buffer) < self._batch_size:
                    try:
                        record = self._queue.get_nowait()
                        self._buffer.append(record)
                    except queue.Empty:
                        break

                if len(self._buffer) >= self._batch_size:
                    self._flush()

            except queue.Empty:
                # Flush interval reached without filling batch
                if self._buffer:
                    self._flush()

    def _flush(self) -> None:
        """Send buffered records to TBO engine."""
        if not self._buffer or not self._engine_url:
            self._buffer.clear()
            return

        batch = self._buffer.copy()
        self._buffer.clear()

        try:
            import httpx

            payload = [record.model_dump(mode="json") for record in batch]
            # Fire and forget — don't retry on failure
            with httpx.Client(timeout=5.0) as client:
                response = client.post(
                    f"{self._engine_url}/v1/telemetry/ingest",
                    json=payload,
                )
                if response.status_code != 200:
                    logger.warning(f"Telemetry send failed: {response.status_code}")
        except Exception as e:
            logger.debug(f"Telemetry send error (non-blocking): {e}")

    def flush_sync(self) -> None:
        """Flush all pending records synchronously. For shutdown/testing."""
        while not self._queue.empty():
            try:
                self._buffer.append(self._queue.get_nowait())
            except queue.Empty:
                break
        self._flush()

    def shutdown(self) -> None:
        """Stop the background worker and flush remaining records."""
        self._stop_event.set()
        if self._worker and self._worker.is_alive():
            self._worker.join(timeout=2.0)
        self.flush_sync()
