# [NAMA PRODUK FINAL] — Technical Document

> Project HAWK-EYE — internal codename. This document describes the local preliminary MVP.

## Background

The product preserves public web evidence before deriving relationship-neutral leads. It addresses
delayed or misleading rendering, provenance loss, unsafe browser automation, opaque model output,
unrecollected candidate URLs, mutable review state, and graph animation that can drift from stored
facts.

## Objective

Provide a localhost-only reproducible path from Page A capture to a human-reviewed candidate
relationship, with deterministic behavior when Codex is unavailable and fixture-based evaluation
that never depends on live gambling or search-result pages.

## Innovation and impact

The implementation combines four independent capture dimensions, browser-visible truth, bounded
semantic evidence crops, snapshot-bound interaction references, capability-gated structured agent
decisions, deterministic fallback, append-only assertion/review history, and an idempotent event
graph. Expected impact is improved auditability for evaluators and investigators. User-time,
accuracy, organizational, or societal impact has not yet been measured.

## Functional description

1. `hawkeye investigate` performs bounded Playwright collection and writes a verified case.
2. Eligible captures write `observations.json`; limited captures do not auto-produce strong
   observations.
3. The controlled fixture runtime exposes six narrow page tools over stable references.
4. `CodexInvestigator` validates one structured decision or activates deterministic fallback.
5. The fixture investigation persists Page A, Page B, lead, assertion, review requirement, and all
   causally linked events in SQLite.
6. The local workspace renders graph, evidence, timeline, causal path, and review state.
7. `hawkeye benchmark` produces raw JSON and all required Markdown result tables.

## Feature details

### Capture readiness

Checkpoint schedule is exactly 0, 500, 1,500, and 3,000 ms after `domcontentloaded`. Canonical state
is 3,000 ms. It collects no `networkidle`, clicks, scrolls, form submissions, consent dismissal, or
downloads. Metrics and limits are documented in `docs/CAPTURE_ADEQUACY.md`.

### Semantic evidence

Fourteen observation types are implemented. Raw and normalized values remain distinct. Claimed
branding explicitly has `verified_ownership: false`. Dictionary-derived payment, offer, and legal
claims are weak. Bounded crops are best-effort and never determine whether the observation exists.

### Interaction policy

The tool executor evaluates the tag/role/label/href/action/form/download/new-tab/destination/keyword
set/budget/snapshot. Stale references, login, register, Contact Us, messages, forms, payment,
downloads, and external application schemes fail closed. Controlled unsafe-action block rate is
1.0000 over four prohibited fixture controls.

### Agent runtime

Only fixed localhost routes are probeable. The selected route is `/v1/responses`; its model and
structured tool capabilities remain unknown, so the model path is disabled. No native search is
assumed. Deterministic fallback produces `AgentDecision` and `AgentStepResult` models identical to
the model path.

### Candidate and review

A URL is a lead until recollection produces a stored candidate page artifact and observation. The
synthetic fixture index may recollect automatically. Real mode requires approval and still leaves
external collection to a separate explicit action. Assertions support public links, shared contact,
redirect, download, referral, brand claim, and generic candidate relation. Reviews support verified,
rejected, needs_more_evidence, duplicate, and uncertain.

### Event-driven graph

Events use monotonic per-run sequence and causation IDs. Duplicate IDs with identical contents are
idempotent; conflicting IDs fail. SQLite triggers reject update/delete operations on events,
candidate leads, assertions, and reviews. The reducer emits graph state plus a separate animation
queue.

## Architecture

| Layer | Implementation | Persistence | Trust boundary |
|---|---|---|---|
| URL safety | `hawkeye/collector/safety.py` | none | validates public HTTP(S), DNS, crawl scope |
| Browser capture | `hawkeye/collector/playwright_collector.py` | filesystem | no interactions; fixed budgets |
| Case pipeline | `hawkeye/pipeline.py` | case JSON/artifacts | extraction eligibility |
| Semantic evidence | `hawkeye/semantic_evidence.py` | observations/crops | public observables only |
| Interaction | `hawkeye/interaction/` | normalized decisions | policy before state change |
| Agent | `hawkeye/agent/` | secret-free diagnostics/events | no direct tool execution |
| Investigation | `hawkeye/investigation/` | SQLite + fixture artifacts | append-only records |
| Graph | `hawkeye/investigation/reducer.py` | derived | events are source of truth |
| Console | `hawkeye/review_app/` | explicit workspace | localhost/Host/origin/CSP controls |
| Evaluation | `hawkeye/benchmark.py` | JSON + Markdown | synthetic fixtures authoritative |

## SQLite schema and migration behavior

The MVP creates `events`, `candidate_leads`, `assertions`, and `reviews` with `CREATE TABLE IF NOT
EXISTS`. There is no destructive migration. Append-only triggers prohibit update/delete. Assertion
status is not mutated; it is calculated from the highest review `new_version`. Existing legacy case
files have optional new capture fields and remain parseable by `CaseLoader`.

## Installation

Requirements: Python 3.12 or newer, a compatible Chromium installed by Playwright, and a loopback
port. Node is needed only for the JavaScript syntax verification gate; the UI has no npm runtime
dependency.

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
python -m playwright install chromium
```

## Configuration

- Production URL collection rejects private/loopback targets.
- Fixture loopback requires `HAWKEYE_TEST_MODE=1` plus explicit CLI flag.
- Local server host is fixed to `127.0.0.1`; only port is configurable.
- Enabling workspace writes requires `--workspace <directory>`.
- Omitting `--workspace` preserves the legacy read-only console.
- Capability probe timeout is 0–5 seconds; model request timeout is capped at 30 seconds.

## Usage

```powershell
python -m hawkeye codex-probe `
  --output verification-output/codex-capabilities.json

python -m hawkeye benchmark `
  --output verification-output/benchmark --agent-attempts 3

python -m hawkeye serve `
  --cases verification-output/demo-cases `
  --workspace verification-output/mvp-workspace `
  --port 8760
```

The UI flow is controlled seed → collect/expand → capture and fallback status → Page B state →
observations/artifacts → candidate assertion → append review → replayed graph/timeline.

## Screenshots

TODO — requires completed test: capture actual final local UI screenshots after the final full gate,
store sanitized images in `gemastik-2026/assets/technical/`, and record exact source run and hash in
`FIGURE_INDEX.md`. No remote image, real-site artifact, personal information, or fake graph may be
inserted.

## Troubleshooting

| Symptom | Meaning | Action |
|---|---|---|
| `fallback_required: true` | Required Codex capabilities were not advertised | Continue with deterministic fallback |
| `blocked_by_policy` | URL/action/resource failed server policy | Inspect limitation/event; do not bypass |
| `captured_with_limitations` | Navigation succeeded but capture adequacy is limited | Inspect readiness; do not auto-assert |
| `direct_extractor_input_exceeds_2_mb` | HTML was preserved but not sent to extractor | Manual bounded inspection only |
| `canonical_html_not_persisted` | HTML exceeded 5 MB | Use visible text/screenshots/readiness; no auto-extraction |
| `stale_reference` | Snapshot or fingerprint changed | Rediscover elements; never reuse selector blindly |
| `waiting_for_approval` | Real candidate is only a lead | Record explicit decision; collection remains separate |
| `case_integrity_error` | Artifact/reference hash validation failed | Do not display or repair silently |
| Host header error | Request was not addressed to localhost/127.0.0.1 | Use the loopback URL directly |

## Security boundaries

The server is not safe for public deployment. It has no multi-user authentication/authorization.
Workspace POST routes require allowed Host and same Origin when Origin is present, but those controls
do not replace authentication on a public network. Captured HTML is served inert; UI code uses text
nodes rather than injecting hostile HTML. Collected web content is data and is never executed as
instructions.

DNS validation has a documented browser-resolution TOCTOU residual. Eliminating it requires a
separately designed validating proxy or network-level IP pinning. The collector does not add stealth,
CAPTCHA bypass, geo bypass, authentication, arbitrary user-agent impersonation, or unbounded delay.

## Verification commands

```powershell
python -m ruff format --check .
python -m ruff check .
python -m mypy hawkeye
python -m pytest -q
node --check hawkeye/review_app/static/app.js
git diff --check
```

Exact final results belong in `IMPLEMENTATION_STATUS.md` and `docs/STATUS.md` after the last run.

