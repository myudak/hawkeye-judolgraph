# Bounded model runtime

`ModelInvestigator` receives only an objective, normalized case state and observations,
server-issued stable element references, a policy/budget summary, prior tool results, and an
explicit evidence gap. It receives no raw shell, Playwright object, filesystem, database mutation
handle, secrets, or unbounded HTML.

The optional transport is configured only by the operator environment:

```text
HAWKEYE_LLM_BASE_URL
HAWKEYE_LLM_API_KEY
HAWKEYE_LLM_MODEL
HAWKEYE_LLM_ENABLED=0|1
HAWKEYE_LLM_API_STYLE=auto|responses|chat_completions
HAWKEYE_LLM_TIMEOUT_SECONDS
```

Set `HAWKEYE_LLM_ENABLED=0` to temporarily disable a stored provider without deleting its endpoint,
model, or API key. The base URL must be HTTPS except for loopback development and
cannot contain credentials, query parameters, or a fragment. Provider redirects are rejected, the
response body is bounded, the timeout is capped, and an API key is sent only to the validated
origin. It is never included in diagnostics, events, UI responses, exception messages, exports, or
repository files.

The landing capability endpoint reads and validates configuration but performs no network request.
Its states distinguish `fallback_only`, `model_configured_unverified`, and
`configuration_invalid`; successful and unavailable states come only from explicit execution or
probe evidence. `hawkeye llm-probe` performs one opt-in strict JSON-schema handshake.

In `auto` mode the client tries the Responses route first. It uses Chat Completions only when that
route returns `404` or `405`; a schema error, authentication error, rate limit, redirect, timeout,
or other HTTP status does not trigger route switching. Both envelopes request strict JSON Schema
and must decode to one `AgentDecision`.

The orchestrator may request at most five decisions and execute at most three policy-approved
interactions for one explicit objective. After each tool result, observation deltas and state
change are fed into the next decision. Stop reasons include objective satisfaction, no safe action,
repeated stale reference, repeated no-op, decision budget, and interaction budget.

A tool request must reproduce an exact server-issued safe reference including its fingerprint.
Free-form prose, invalid schema, mutated references, transport failures, redirects, oversized
responses, and timeouts fail closed. After bounded failures, deterministic fallback emits the same
decision schema and selects only a server-policy-permitted public action. Neither path executes a
tool directly, verifies an assertion, or infers ownership, identity, criminality, or legality.

The 2026-08-03 `gpt-5.6-terra` Codex-LB handshake and QQ run remain historical validation. They are
not a current installation requirement, fixture benchmark, or permission to persist credentials.
