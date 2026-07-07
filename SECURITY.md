# Security

## Trust architecture

Token Budget Orchestrator uses a zero-trust data model. The SDK runs in your process, and prompts never leave your infrastructure.

### SDK (local)

- Runs entirely in your process
- Prompts and responses stay in your environment
- API keys pass directly to the LLM provider, never stored or transmitted by TBO
- Budget enforcement and policy evaluation happen locally (~5ms overhead)

### Engine (optional, self-hosted)

- Receives only aggregated metadata: token counts, costs, latency, model name
- Never receives prompt content, response content, or API keys
- Authenticated via API key (`X-TBO-API-Key` header)
- CORS restricted to configured origins
- All identifiers validated against `[a-zA-Z0-9_\-\.]+`

### What the engine sees vs. what it does not

Collected: token count (input/output), model name, estimated cost, latency, agent ID, timestamp.

Not collected: prompt content, response content, API keys, user PII, business data, file contents.

## Reporting vulnerabilities

If you find a security issue, open a [private security advisory](https://github.com/ricmmartins/tokenbudgetorchestrator/security/advisories/new) on this repository. Include a description, steps to reproduce, and your assessment of impact.

You can also email ricmmartins@gmail.com directly.

## Security controls

- Input validation: all path parameters match `[a-zA-Z0-9_\-\.]+`, max 128 chars
- Budget integrity: Lua scripts reject negative values; reservation pattern prevents race conditions
- Authentication: API key required for all state-modifying engine endpoints
- No secrets in code: all sensitive config via environment variables
- Minimal dependencies: small dependency tree to reduce supply chain risk
