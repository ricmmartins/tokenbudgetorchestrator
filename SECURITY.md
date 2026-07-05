# Security

## Trust Architecture

Token Budget Orchestrator is designed with a **zero-trust data model**:

### SDK (Local)
- Runs entirely in your process/infrastructure
- Prompts and responses **never** leave your environment
- API keys are passed directly to the LLM provider — never stored or transmitted by TBO
- Budget enforcement and policy evaluation happen locally (< 5ms overhead)

### Engine (Optional, Self-hostable)
- Only receives **aggregated metadata**: token counts, costs, latency, model used
- Never receives prompt content, response content, or API keys
- Authenticated via API key (`X-TBO-API-Key` header)
- CORS restricted to configured origins only
- All identifiers validated (workspace, agent_id) to prevent injection

### What We Collect (Telemetry)
| Collected | NOT Collected |
|-----------|---------------|
| Token count (input/output) | Prompt content |
| Model name | Response content |
| Estimated cost (USD) | API keys |
| Latency (ms) | User PII |
| Agent ID | Business data |
| Timestamp | File contents |

## Reporting Vulnerabilities

If you discover a security vulnerability, please report it responsibly:

1. **Do NOT** open a public GitHub issue
2. Email: security@tokenbudgetorchestrator.dev (or open a private security advisory on GitHub)
3. Include: description, reproduction steps, impact assessment
4. We will acknowledge within 48 hours and provide a fix timeline

## Security Controls

- **Input validation**: All path parameters validated against `[a-zA-Z0-9_\-\.]+`
- **Budget integrity**: Lua scripts reject negative values; reservation pattern prevents TOCTOU races
- **Authentication**: API key required for all state-modifying engine endpoints
- **No secrets in code**: All sensitive config via environment variables
- **Dependency minimalism**: Minimal dependency tree to reduce supply chain risk
