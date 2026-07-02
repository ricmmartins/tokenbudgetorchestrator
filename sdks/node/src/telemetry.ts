import type { UsageRecord } from "./models.js";

/**
 * Async telemetry collector. NEVER sends prompt content.
 * Batches metadata records and sends to TBO engine in background.
 */
export class TelemetryCollector {
  private queue: UsageRecord[] = [];
  private engineUrl?: string;
  private batchSize: number;
  private flushInterval: number;
  private timer?: ReturnType<typeof setInterval>;
  private enabled: boolean;

  constructor(options: {
    engineUrl?: string;
    batchSize?: number;
    flushIntervalMs?: number;
    enabled?: boolean;
  } = {}) {
    this.engineUrl = options.engineUrl;
    this.batchSize = options.batchSize ?? 10;
    this.flushInterval = options.flushIntervalMs ?? 5000;
    this.enabled = options.enabled ?? true;

    if (this.enabled && this.engineUrl) {
      this.timer = setInterval(() => this.flush(), this.flushInterval);
      this.timer.unref(); // Don't block Node.js exit
    }
  }

  record(usage: UsageRecord): void {
    if (!this.enabled) return;
    this.queue.push(usage);
    if (this.queue.length >= this.batchSize) {
      this.flush();
    }
  }

  flush(): void {
    if (this.queue.length === 0 || !this.engineUrl) {
      this.queue = [];
      return;
    }

    const batch = [...this.queue];
    this.queue = [];

    // Fire and forget — non-blocking
    fetch(`${this.engineUrl}/v1/telemetry/ingest`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(batch),
      signal: AbortSignal.timeout(5000),
    }).catch(() => {
      // Silently drop on failure — telemetry should never break the app
    });
  }

  shutdown(): void {
    if (this.timer) clearInterval(this.timer);
    this.flush();
  }

  /** For testing: get queue size */
  get pendingCount(): number {
    return this.queue.length;
  }

  /** For testing: get last queued record */
  get lastRecord(): UsageRecord | undefined {
    return this.queue[this.queue.length - 1];
  }
}
