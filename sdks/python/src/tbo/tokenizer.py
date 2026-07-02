"""Local token counting — estimates tokens without sending content externally."""

from __future__ import annotations

from tbo.models import Provider


class TokenCounter:
    """Counts tokens locally using provider-specific tokenizers.

    NEVER sends content to any external service. All counting is local.
    """

    def __init__(self, provider: Provider):
        self._provider = provider
        self._encoder = None

    def _get_encoder(self):
        if self._encoder is None:
            if self._provider == Provider.OPENAI:
                import tiktoken

                self._encoder = tiktoken.encoding_for_model("gpt-4o")
            elif self._provider == Provider.ANTHROPIC:
                # Anthropic uses a similar BPE tokenizer; tiktoken cl100k_base
                # is a reasonable approximation (~5% margin)
                import tiktoken

                self._encoder = tiktoken.get_encoding("cl100k_base")
        return self._encoder

    def count(self, text: str | list) -> int:
        """Count tokens in text or message list.

        Args:
            text: A string or list of message dicts [{"role": ..., "content": ...}]

        Returns:
            Estimated token count (local only, never sends data out).
        """
        if isinstance(text, str):
            return self._count_string(text)
        elif isinstance(text, list):
            return self._count_messages(text)
        return 0

    def _count_string(self, text: str) -> int:
        encoder = self._get_encoder()
        if encoder is None:
            # Fallback: ~4 chars per token heuristic
            return len(text) // 4
        return len(encoder.encode(text))

    def _count_messages(self, messages: list) -> int:
        total = 0
        for msg in messages:
            # Per-message overhead (~4 tokens for role + formatting)
            total += 4
            content = msg.get("content", "")
            if isinstance(content, str):
                total += self._count_string(content)
            elif isinstance(content, list):
                # Multi-modal messages
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        total += self._count_string(block.get("text", ""))
                    # Image blocks: estimate based on typical vision token usage
                    elif isinstance(block, dict) and block.get("type") == "image":
                        total += 765  # Approximate for standard image
        # Reply priming
        total += 3
        return total

    def estimate_cost(
        self, input_tokens: int, output_tokens: int, model: str, pricing_table: dict
    ) -> float:
        """Estimate cost in USD based on token counts and pricing."""
        pricing = pricing_table.get(model)
        if pricing is None:
            return 0.0
        input_cost = (input_tokens / 1_000_000) * pricing.input_per_million
        output_cost = (output_tokens / 1_000_000) * pricing.output_per_million
        return input_cost + output_cost
