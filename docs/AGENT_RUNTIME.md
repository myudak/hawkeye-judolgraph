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

If the local service requires a credential, set `HAWKEYE_CODEX_LB_API_KEY` in the server process
environment. The probe and gated client send it only as an `Authorization: Bearer` request header;
they never include it in diagnostics, events, UI responses, exception messages, or repository
files. A reachable route is still insufficient: model execution remains disabled unless the probe
advertises structured output, function calls, and tool-result continuation.

All model decisions must validate as `AgentDecision`; free-form prose is rejected. Two invalid or
failed attempts activate deterministic fallback. The fallback emits the same decision schema and
selects the first server-policy-permitted public action, otherwise stops. Neither path executes a
tool directly, writes evidence, verifies an assertion, infers ownership, or infers criminality.
Native search is not a dependency. Direct links, redirects, new tabs, and iframe destinations come
first; controlled search uses only the deterministic fixture index.
