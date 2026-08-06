# Bounded Agent Runtime

`CodexInvestigator` receives only an objective, normalized case state and observations, stable safe
element map, policy/budget summary, prior tool results, and explicit evidence gap. It receives no
raw shell, Playwright object, HTTP client, filesystem, database mutation handle, secrets, or
unbounded HTML.

The capability probe touches only two fixed loopback routes. For `/v1/responses`, it discovers an
available model from `/v1/models` and verifies strict JSON-schema output with a bounded live probe.
On 2026-08-03 the local service selected `gpt-5.6-terra`; a structured decision call succeeded and
the live QQ validation used Codex. Function-call continuation, streaming, cancellation, and native
search are not required because the model returns one decision at a time and never executes a tool.
The orchestrator may request at most five decisions and execute at most three policy-approved
interactions for one explicit objective. After each tool result, added/removed observations and the
state-change flag are fed into the next decision. Objective satisfaction, no safe action, repeated
stale reference, repeated no-op, decision budget, and interaction budget are explicit stop reasons. When
structured output cannot be verified, the same runtime records the failure and uses its
deterministic fallback. Diagnostics remain secret-free.

If the local service requires a credential, set `HAWKEYE_CODEX_LB_API_KEY` in the server process
environment. The probe and gated client send it only as an `Authorization: Bearer` request header;
they never include it in diagnostics, events, UI responses, exception messages, or repository
files. A reachable route alone remains insufficient: model execution is enabled only after model
discovery and the strict structured-output probe both succeed.

All model decisions must validate as a strict `AgentDecision`; free-form prose is rejected. A tool
request must reproduce an exact server-issued safe reference, including its fingerprint. Two
invalid or failed attempts activate deterministic fallback. The fallback emits the same decision schema and
selects the next server-policy-permitted public action, otherwise stops. Attempted references are
excluded from later iterations. Neither path executes a
tool directly, writes evidence, verifies an assertion, infers ownership, or infers criminality.
Native search is not a dependency. Direct links, redirects, new tabs, and iframe destinations come
first; controlled search uses only the deterministic fixture index.
