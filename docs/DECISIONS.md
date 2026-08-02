# Architecture and Scope Decisions

## ADR-001 — Deterministic evidence pipeline

**Status:** accepted

Collection, extraction, candidate generation, and comparison use explicit deterministic rules and
persist provenance. AI may assist a future workflow only inside a separately documented,
evidence-backed boundary.

## ADR-002 — Leads are not conclusions

**Status:** accepted

Candidates remain `pending` with `relationship: null`; comparison emits an evidence-similarity
score with `needs_review`. Neither output may be labelled ownership, mirror confirmation, or
criminal attribution.

## ADR-003 — Bounded public collection

**Status:** accepted

Collection permits public HTTP(S) seeds only, applies URL and DNS safety checks, and remains bounded
to same-site depth `0..1` and five HTML pages. It does not log in, submit forms, accept downloads,
or bypass restrictions. Candidate domains are never crawled automatically.

## ADR-004 — Local-only V1 console

**Status:** accepted

The review console binds only to `127.0.0.1`, permits only `127.0.0.1` and `localhost` Host
headers, ignores forwarded-host headers, has no CORS or write endpoints, and re-verifies artifacts
before delivery. Public deployment requires a new threat model, authentication, authorization, and
review milestone.

## ADR-005 — Reviewer conversation is advisory

**Status:** accepted

The designated Chrome conversation is a lead-agent-only architecture and security checkpoint.
Repository artifacts and executed verification take precedence. The conversation is neither shared
memory nor an execution worker, and it receives no secrets or large raw artifacts.

## ADR-006 — Live evaluation is opt-in and non-interactive

**Status:** accepted

Live public URLs are recorded as manifests and may be observed or collected only through bounded
non-interactive workflows. They are not unit-test truth. Raw captures remain ignored local data
unless redistribution is separately justified; deterministic fixtures are the test source of truth.

## ADR-007 — Residual DNS TOCTOU is documented

**Status:** accepted

The collector revalidates request destinations, but Chromium ultimately resolves hostnames itself.
Complete DNS-rebinding elimination would require network-layer IP pinning or a validating proxy.
This residual limitation is documented rather than hidden.

## ADR-008 — Rendered-content completeness is a separate capture concern

**Status:** accepted

Chrome observations of two opt-in live evaluations showed more visible landing-page content than
the isolated collector artifacts, which preserved title-led sparse shells and dark screenshots.
This is recorded as a rendered-content completeness gap, not as a challenge, failure, mirror, or
site conclusion. G0 adds a fully local delayed-render shell fixture but does not change collection,
classification, waiting, user-agent, screenshot, or scoring behavior; any fix belongs to G1.

## ADR-009 — G1 diagnostics are isolated and fixed-time

**Status:** accepted

G1 may create an opt-in `diagnostics/render-diagnostics.json` under an already-verified local
case. It re-navigates only the saved same-site page in a fresh non-interactive context and records
neutral measurements at `0`, `500`, `1500`, and `3000` milliseconds. The three-second wait budget
is fixed and does not adapt to a page. Diagnostics reference canonical evidence but do not modify
or replace canonical HTML, screenshots, classification, entities, graph edges, candidates, or
comparison scores. They do not determine why a page changed.

## ADR-010 — G2 presents verified artifacts without creating review facts

**Status:** accepted

G2 may improve the localhost investigator console only by projecting already verified local case
data. Every shown entity, graph edge, candidate reason, and comparison component carries a visible
case/evidence/observation reference when it is locally available. Captured HTML remains an inert
`text/plain` attachment and all hostile artifact values are bounded text, never inserted as HTML or
converted to remote links.

Optional comparison documents live in a separately configured local directory. Before display, the
console verifies both referenced case manifests, each evidence path/hash, and entity references;
an invalid document becomes an integrity warning rather than a displayed score. Optional G1
diagnostics are separately validated against the current case manifest and remain explicitly
noncanonical. The UI has no write route, review-decision store, remote asset, external fetch,
collection trigger, scoring change, or public bind.

## ADR-011 — G3 verifies a frozen runtime through an external evaluator wrapper

**Status:** accepted

G3 targets the `gemastik-g2` tag at `e55c1610c4e5a0a31891e3a69944aa1ffe2648ac`. Its verifier is a
checked-in script, not an engine or API change. Before producing a report, it checks that the tag
still resolves to the target and that the `hawkeye/` runtime tree has not drifted from G2. G3
documentation, labels, scripts, and tests are intentionally outside that frozen runtime boundary.

The verifier creates a new sanitized demo directory under caller-selected ignored output, blocks
normal DNS/socket connection primitives while it builds and reads fixture inputs, validates case and
comparison references through the existing loader, checks hash-backed labels, and writes a report
outside immutable case directories. It refuses an existing output directory and returns nonzero for
required failures. Its report distinguishes `PASS`, `FAIL`, `NOT APPLICABLE`, and
`OBSERVATIONAL ONLY`; no live result becomes permanent benchmark truth.
