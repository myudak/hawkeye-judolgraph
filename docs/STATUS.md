# Project Status

## Current milestone

**G1 — Rendered-content completeness diagnostics** is complete. It remains isolated from the
canonical V0–V1 collector and has no authority to change its output. Any G2 canonical-capture
change requires a new decision.

## Verified baseline

- Git baseline: `f6fc7ac` (`v1.0.0-baseline`).
- `python -m ruff format --check .` — passed.
- `python -m ruff check .` — passed.
- `python -m mypy hawkeye` — passed.
- `python -m pytest -q` — 115 passed on 2026-08-02.
- A local V1 server demonstration verified loopback access, strict CSP, safe artifact headers, and
  rejection of a hostile Host header.

## Current capabilities

The repository includes V0 through V0.4 and V1 as listed in `docs/ROADMAP.md`. A previous opt-in
live run against `https://www.888.com/` completed locally; its raw case and discovery artifacts are
kept under ignored `verification-output/` and are not benchmark truth.

## Known limitations

- Live sites can change by time, geography, VPN exit, challenge state, or session state.
- Chromium performs its own hostname resolution after application-level DNS validation; see
  ADR-007 for the residual DNS TOCTOU limitation.
- The V1 console is intentionally a single-machine localhost viewer, not a public service.
- Candidate and similarity output require human review and do not establish ownership or legal
  conclusions.
- The two opt-in live evaluations completed, but rendered-content completeness is uncertain: their
  saved DOMs and screenshots contained substantially less visible content than separate Chrome
  observations. This is environment-dependent qualitative evidence, not live-site truth. A fully
  local delayed-render shell fixture records the current behavior; any engine change is deferred to
  G1.
- In two opt-in G1 diagnostic passes, separately loaded pages changed substantially within the
  fixed three-second wait budget after initially sparse measurements. This is an
  environment-dependent observation; it does not establish a cause, prove a later checkpoint is
  canonical, or authorize a collector-wait change.

## Next checkpoint

Before G2 begins, define a narrow proposal for whether—and how—bounded readiness diagnostics could
affect canonical capture. A separate decision is required before changing collection timing,
canonical artifact selection, classification, user-agent behavior, screenshots, or scoring.
