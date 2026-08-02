# Project Status

## Current milestone

**G2 — Competition investigator workflow** is complete. The localhost console now gives a judge or
investigator a traceable, accessibility-first path through only verified local evidence. It remains
read-only: G2 did not change collection, diagnostic timing, canonical artifacts, extraction, graph
semantics, candidate generation, comparison scoring, bind address, or deployment scope.

## Verified baseline

- Git baseline: `f6fc7ac` (`v1.0.0-baseline`).
- `python -m ruff format --check .` — passed.
- `python -m ruff check .` — passed.
- `python -m mypy hawkeye` — passed.
- `python -m pytest -q` — 121 passed on 2026-08-02.
- A local V1 server demonstration verified loopback access, strict CSP, safe artifact headers, and
  rejection of a hostile Host header.

## Current capabilities

The repository includes V0 through V0.4 and V1 as listed in `docs/ROADMAP.md`. A previous opt-in
live run against `https://www.888.com/` completed locally; its raw case and discovery artifacts are
kept under ignored `verification-output/` and are not benchmark truth.

G2 adds a documented offline judge walkthrough: `python -m hawkeye demo --output <new-directory>`
creates three sanitized fixture cases, one separately verified comparison, and a noncanonical
diagnostic cue. `hawkeye serve --cases <...> --comparisons <...>` displays them through the same
verified loader and localhost-only UI as ordinary cases. See `docs/DEMO.md`.

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
  local delayed-render shell fixture records the current behavior; no collector behavior has been
  changed on the basis of this observation.
- In two opt-in G1 diagnostic passes, separately loaded pages changed substantially within the
  fixed three-second wait budget after initially sparse measurements. This is an
  environment-dependent observation; it does not establish a cause, prove a later checkpoint is
  canonical, or authorize a collector-wait change.

## Next checkpoint

G3 remains proposed, not approved: package a concise evaluator guide, deterministic benchmark
labels, threat-model visual, and presentation narrative around the verified G0–G2 artifacts. Any
future change to collection timing, canonical artifact selection, classification, user-agent
behavior, screenshots, scoring, external network behavior, or public deployment needs a separate
decision.
