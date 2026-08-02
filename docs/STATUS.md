# Project Status

## Current milestone

**G4A–G9 — GEMASTIK preliminary MVP** is implemented and locally verified. The product now combines
capture adequacy, semantic evidence, ten controlled safe-expansion scenarios, a capability-gated
Codex path with deterministic fallback, approval-gated live candidate recollection, append-only human review,
a WebGraph-informed 2D canvas over event-reduced truth, a three-mode benchmark, one bounded
12-target live robustness matrix, and a truthful Markdown submission package. G2/G3 tags and
commits remain unchanged.

## Verification snapshot

Run on 2026-08-03 (Asia/Jakarta) from branch `codex/gemastik-preliminary-mvp-48d4`:

- `python -m ruff format --check .` — passed, 122 files already formatted.
- `python -m ruff check .` — passed.
- `python -m mypy hawkeye` — passed, 60 source files.
- `node --check hawkeye/review_app/static/app.js` — passed.
- `python -m pytest -q` — 169 passed in 492.74 seconds; one upstream FastAPI/Starlette
  deprecation warning.
- `git diff --check` — passed.
- `python -m hawkeye benchmark --output <new-directory> --agent-attempts 3` — passed: ten
  fixtures, 30 agent-fallback attempts, unsafe-action block rate 1.0.
- `python -m hawkeye demo --output <new-directory>` — passed: three legacy sanitized cases and
  one verified offline comparison generated.
- Localhost UI walkthrough — passed: the final QQ run opened by default with two captured same-site
  pages, initial/canonical/full-page screenshot evidence, 11 semantic observations, one real Codex
  action, a direct candidate waiting for approval, and an 11-node/9-link evidence graph. Its still-
  changing final render is truthfully limited while useful text remains provisional evidence.
  Sanitized scenario 6 collapses duplicate URL identities into a compact three-node/three-link
  graph, keeps the review assertion dashed until append-only verification, and scenario 8 exposes
  two persisted policy-preflight blocks with `executed=false`. Six current fixture figures were
  captured at 1280×720 and hash-indexed.

## Implemented product boundary

- Canonical collection always uses 0/500/1500/3000 ms checkpoints and may extend observation to
  5000/8000 ms for an information-rich page still changing at the base boundary.
- Capture access, adequacy, extraction eligibility, and public status are separate fields.
- New capture artifacts are hash/size/type verified by the legacy local loader.
- Semantic observations are public observables, not assertions; crop generation is best effort.
- Interaction tools use snapshot-bound references and a one-action evidence-gap budget.
- The current codex-lb probe discovers `gpt-5.6-terra` and verifies strict structured output. The
  final QQ validation used Codex; transport/schema/reference failure remains a logged fallback.
- Synthetic recollection and live direct-link recollection are implemented. A live candidate is
  collected once only after `candidate_page.approved`; generated candidates are never auto-crawled.
- Assertions and reviews are append-only; current review status is derived from history.
- Graph truth is reduced from persisted events; canvas force motion, particles, minimap, and replay
  never create graph truth. The canvas excludes diagnostic artifact nodes; initial/canonical/full
  screenshots and artifacts remain in the inspector.
- The official benchmark is synthetic and measures observable/task/policy behavior only.

## Known limitations and human-owned completion

- The 12 live observations vary by geography, VPN exit, challenge, session, and time; they remain
  ignored local artifacts and are not test truth.
- The final owner-authorized QQ validation captured two same-site pages, 11 provisional semantic
  observations, a Codex-selected `/Promotion` action, and one approval-gated `qq101uok.com` lead.
- Chromium DNS validation retains the documented TOCTOU residual risk.
- Capture thresholds and interaction coverage are calibrated only on controlled fixtures.
- No image OCR, universal live-web safety guarantee, ownership probability, operator identification,
  criminality, or legal conclusion is claimed.
- The console remains localhost-only and single-machine; review labels are not authenticated users.
- Final name, team/institution/category/advisor, external citations, publication/originality
  confirmations, dependency-license legal review, official formatting, video,
  signatures, PDF export, and upload require authorized humans. They are tracked in
  `gemastik-2026/SUBMISSION_CHECKLIST.md`.

## Local implementation commits

- `ad6b917` — capture adequacy and semantic evidence.
- `cf648e8` — bounded expansion, agent fallback, investigation, event graph, benchmark, and UI.
- `4944659` — compatibility, integrity verification, and historical-tag checks.
- `0917a77` — approval-gated controlled fixture recollection.
- `048641c` / `3acbbf8` — screenshot-first 2D canvas, minimap, replay, and safe walkthrough.
- `f6d5737` — bounded transient probe retry.
- `0dc6d52` / `445079c` — blocked policy preflight events and timeline event inspector.

The package/final-status commit is recorded in the delivery handoff. Nothing is pushed or deployed.
