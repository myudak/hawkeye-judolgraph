# Project Status

## Current milestone

**G0 — Governance and reproducible evaluation baseline** is complete. The next proposed scope is
G1 rendered-content completeness diagnostics; it is not approved or implemented.

## Verified baseline

- Git baseline: `f6fc7ac` (`v1.0.0-baseline`).
- `python -m ruff format --check .` — passed.
- `python -m ruff check .` — passed.
- `python -m mypy hawkeye` — passed.
- `python -m pytest -q` — 103 passed on 2026-08-02.
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

## Next checkpoint

Before G1 begins, define a narrow proposal for bounded rendered-content completeness diagnostics,
including reproducible indicators and timing budgets. Do not change collection, classification,
screenshots, user-agent behavior, or scoring until that proposal is reviewed.
