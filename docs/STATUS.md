# Project Status

## Current milestone

**G3 — Frozen Gemastik evaluator package** is complete. The competition package wraps the frozen
G2 runtime in a fail-closed, hash-backed offline verifier, judge guide, checklist, threat model, and
presentation storyboard. It adds no engine behavior: collection, diagnostic timing, canonical
artifacts, extraction, graph semantics, candidate generation, comparison scoring, bind address,
and deployment scope remain unchanged.

## Verified baseline

- Git baseline: `f6fc7ac` (`v1.0.0-baseline`).
- `python -m ruff format --check .` — passed.
- `python -m ruff check .` — passed.
- `python -m mypy hawkeye` — passed.
- `python -m pytest -q` — 126 passed on 2026-08-02.
- A local V1 server demonstration verified loopback access, strict CSP, safe artifact headers, and
  rejection of a hostile Host header.
- Frozen competition target: `gemastik-g2` /
  `e55c1610c4e5a0a31891e3a69944aa1ffe2648ac`.
- `python scripts/verify_gemastik_demo.py --output <new-directory>` — passed on 2026-08-02,
  including fixture-label, artifact-integrity, pytest, ruff, mypy, and `git diff --check` gates.

## Current capabilities

The repository includes V0 through V0.4 and V1 as listed in `docs/ROADMAP.md`. A previous opt-in
live run against `https://www.888.com/` completed locally; its raw case and discovery artifacts are
kept under ignored `verification-output/` and are not benchmark truth.

G2 adds a documented offline judge walkthrough: `python -m hawkeye demo --output <new-directory>`
creates three sanitized fixture cases, one separately verified comparison, and a noncanonical
diagnostic cue. `hawkeye serve --cases <...> --comparisons <...>` displays them through the same
verified loader and localhost-only UI as ordinary cases. See `docs/DEMO.md`.

G3 adds a fully offline evaluator package under `docs/evaluator/`, a fixture-only label manifest,
an implemented threat model, and a 12-scene presentation storyboard. Its verifier creates a fresh
sanitized demo, validates the frozen runtime and hashes, writes only a separate report directory,
and fails nonzero when a required check is not met. See `docs/evaluator/JUDGE-GUIDE.md`.

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

## Future scope boundary

The Gemastik package is complete at G3. Any future change to collection timing, canonical artifact
selection, classification, user-agent behavior, screenshots, scoring, external network behavior,
or public deployment needs a separate decision and must not be folded into this frozen evaluator
package.
