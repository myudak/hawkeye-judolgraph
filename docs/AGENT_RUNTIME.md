# Bounded Agent Runtime

`CodexInvestigator` receives only an objective, normalized case state and observations, stable safe
element map, policy/budget summary, prior tool results, and explicit evidence gap. It receives no
raw shell, Playwright object, HTTP client, filesystem, database mutation handle, secrets, or
unbounded HTML.

The capability probe sends bounded empty POST requests only to the two fixed loopback routes. The
2026-08-02 local probe found `/backend-api/codex` unsupported for POST (405) and `/v1/responses`
present but requiring a model field (400). No model or structured-output, tool continuation,
streaming, cancellation, or native-search capability was advertised. Those capabilities remain
`unknown`; model execution is disabled and deterministic fallback is required. Secret-free raw
diagnostics are under ignored `verification-output/g4-g9/`.

All model decisions must validate as `AgentDecision`; free-form prose is rejected. Two invalid or
failed attempts activate deterministic fallback. The fallback emits the same decision schema and
selects the first server-policy-permitted public action, otherwise stops. Neither path executes a
tool directly, writes evidence, verifies an assertion, infers ownership, or infers criminality.
Native search is not a dependency. Direct links, redirects, new tabs, and iframe destinations come
first; controlled search uses only the deterministic fixture index.

