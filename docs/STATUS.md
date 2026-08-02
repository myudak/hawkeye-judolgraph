# Project Status

## Current milestone

**G4A–G9 — GEMASTIK preliminary MVP** is implemented and locally verified. The product now combines
capture adequacy, semantic evidence, ten controlled safe-expansion scenarios, a capability-gated
Codex path with deterministic fallback, synthetic candidate recollection, append-only human review,
a WebGraph-informed 2D canvas over event-reduced truth, a three-mode benchmark, one bounded
12-target live robustness matrix, and a truthful Markdown submission package. G2/G3 tags and
commits remain unchanged.

## Verification snapshot

Run on 2026-08-03 (Asia/Jakarta) from branch `codex/gemastik-preliminary-mvp-48d4`:

- `python -m ruff format --check .` — passed, 118 files formatted.
- `python -m ruff check .` — passed.
- `python -m mypy hawkeye` — passed, 59 source files.
- `node --check hawkeye/review_app/static/app.js` — passed.
- `python -m pytest -q` — 158 passed in 380.88 seconds; one upstream FastAPI/Starlette
  deprecation warning.
- `git diff --check` — passed.
- `python -m hawkeye benchmark --output <new-directory> --agent-attempts 3` — passed: ten
  fixtures, 30 agent-fallback attempts, unsafe-action block rate 1.0.
- `python -m hawkeye demo --output <new-directory>` — passed: three legacy sanitized cases and
  one verified offline comparison generated.
- Localhost UI walkthrough — passed: scenario 6 produced Page A → Page B, a dashed assertion,
  append-only verified review, 18-event replay, and a `solid_emphasized` edge. Visual QA also
  covered the responsive workspace layout.

## Implemented product boundary

- Canonical collection waits only at fixed checkpoints and never adapts or interacts.
- Capture access, adequacy, extraction eligibility, and public status are separate fields.
- New capture artifacts are hash/size/type verified by the legacy local loader.
- Semantic observations are public observables, not assertions; crop generation is best effort.
- Interaction tools use snapshot-bound references and a one-action evidence-gap budget.
- The current codex-lb probe does not establish required model capability; official behavior is the
  logged deterministic fallback, not a hidden model claim.
- Synthetic candidate recollection is implemented. Approval-gated controlled runs persist approval
  before fixture recollection; external candidates are never collected by that action.
- Assertions and reviews are append-only; current review status is derived from history.
- Graph truth is reduced from persisted events; canvas force motion, particles, minimap, and replay
  never create graph truth. Saved-case screenshots and all artifact links remain in the inspector.
- The official benchmark is synthetic and measures observable/task/policy behavior only.

## Known limitations and human-owned completion

- The 12 live observations vary by geography, VPN exit, challenge, session, and time; they remain
  ignored local artifacts and are not test truth.
- Chromium DNS validation retains the documented TOCTOU residual risk.
- Capture thresholds and interaction coverage are calibrated only on controlled fixtures.
- No image OCR, universal live-web safety guarantee, ownership probability, operator identification,
  criminality, or legal conclusion is claimed.
- The console remains localhost-only and single-machine; review labels are not authenticated users.
- Final name, team/institution/category/advisor, external citations, publication/originality
  confirmations, dependency-license legal review, official formatting, screenshots, video,
  signatures, PDF export, and upload require authorized humans. They are tracked in
  `gemastik-2026/SUBMISSION_CHECKLIST.md`.

## Local implementation commits

- `ad6b917` — capture adequacy and semantic evidence.
- `cf648e8` — bounded expansion, agent fallback, investigation, event graph, benchmark, and UI.
- `4944659` — compatibility, integrity verification, and historical-tag checks.

The package/final-status commit is recorded in the delivery handoff. Nothing is pushed or deployed.
