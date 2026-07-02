import type { Provider } from "./models.js";

export class TokenCounter {
  private provider: Provider;

  constructor(provider: Provider) {
    this.provider = provider;
  }

  /**
   * Count tokens in messages locally. NEVER sends content externally.
   * Uses ~4 chars/token heuristic (accurate within ~10% for English text).
   * For production accuracy, use tiktoken via WASM binding.
   */
  count(messages: Array<{ role: string; content: string | unknown[] }>): number {
    let total = 0;
    for (const msg of messages) {
      total += 4; // per-message overhead
      if (typeof msg.content === "string") {
        total += this.countString(msg.content);
      } else if (Array.isArray(msg.content)) {
        for (const block of msg.content) {
          if (typeof block === "object" && block !== null && "type" in block) {
            const b = block as Record<string, unknown>;
            if (b.type === "text" && typeof b.text === "string") {
              total += this.countString(b.text);
            } else if (b.type === "image") {
              total += 765;
            }
          }
        }
      }
    }
    total += 3; // reply priming
    return total;
  }

  countString(text: string): number {
    // ~4 chars per token heuristic. For better accuracy,
    // integrate tiktoken-wasm or gpt-tokenizer package.
    return Math.ceil(text.length / 4);
  }

  estimateCost(
    inputTokens: number,
    outputTokens: number,
    pricing: { inputPerMillion: number; outputPerMillion: number }
  ): number {
    return (
      (inputTokens / 1_000_000) * pricing.inputPerMillion +
      (outputTokens / 1_000_000) * pricing.outputPerMillion
    );
  }
}
