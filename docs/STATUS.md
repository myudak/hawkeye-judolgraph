# Project Status

## Current milestone

**G4A–G9 — GEMASTIK preliminary MVP plus post-G9 investigator hardening** is implemented and locally verified. The product now combines
capture adequacy, optional bounded OCR, ten controlled safe-expansion scenarios, a capability-gated
multi-step Codex path with deterministic fallback, approval-gated live candidate recollection,
exact cross-case assertions, temporal diffs, append-only human review, a WebGraph-informed 2D canvas
over event-reduced truth, explainable integer judol-indicator counts, recoverable progressive scan
jobs with a killable browser boundary, a three-mode benchmark, one bounded
12-target live robustness matrix, and a truthful Markdown submission package. G2/G3 tags and
commits remain unchanged.

## Verification snapshot

Run on 2026-08-08 (Asia/Jakarta) from branch `codex/gemastik-preliminary-mvp-48d4`:

- `python -m ruff format --check .` — passed, 132 files already formatted.
- `python -m ruff check .` — passed.
- `python -m mypy hawkeye` — passed, 65 source files.
- `node --check hawkeye/review_app/static/app.js` — passed.
- `python -m pytest -q` — 190 passed in 470.26 seconds; one upstream FastAPI/Starlette
  deprecation warning.
- `git diff --check` — passed.
- `python -m hawkeye benchmark --output verification-output/postg9-indicators-benchmark-20260808 --agent-attempts 3` — passed: ten
  fixtures, 30 agent-fallback attempts, unsafe-action block rate 1.0.
- `python -m hawkeye demo --output verification-output/postg9-indicators-demo-20260808` — passed: three legacy sanitized cases and
  one verified offline comparison generated.
- Localhost UI walkthrough — passed: the final QQ run opened by default with two captured same-site
  pages, initial/canonical/full-page screenshot evidence, 11 seed/crawl semantic observations, one
  real Codex-selected Contact action, a direct candidate waiting for approval, and an 11-node/10-
  link evidence graph. The `/Contact` route carries screenshot/HTML/text/JSON artifacts and three
  distinct public-contact observations: telephone `+639543355092`, WhatsApp
  `https://wa.me/639543355092`, and Telegram `+639157800101`. Its still-changing final render is
  truthfully limited while useful text remains provisional evidence. A fresh 888 run produced a
  26-node/25-link graph with claim categories separated from contacts and prioritized approval leads
  for `888casino.com`, `888poker.com`, and `888sport.com`.
  Sanitized scenario 6 collapses duplicate URL identities into a compact three-node/three-link
  graph, keeps the review assertion dashed until append-only verification, and scenario 8 exposes
  two persisted policy-preflight blocks with `executed=false`. Six current fixture figures were
  captured at 1280×720 and hash-indexed.
- Post-G9 browser QA — passed: saved QQ rendered an 11-node/12-link graph, full-page screenshot by
  default, 20 semantic observations, and six explainable judol indicators; saved 888 rendered a
  26-node/25-link graph, 25 indicators, and direct public links to the three 888 product domains.
  Landing/workspace/summary had no horizontal overflow or console errors. One fresh authorized QQ
  validation stayed in browser capture under the current network and was truthfully terminated at
  the 115-second hard boundary; the animated UI displayed the final stop reason instead of hanging.

React presentation refresh verified on 2026-08-10 (Asia/Jakarta):

- The shadcn/Vite frontend builds into the existing loopback FastAPI static directory with a
  224.78 kB entry (69.30 kB gzip) and lazy landing, scan, workspace, and summary route chunks.
- `npm run format:check`, `npm run lint`, `npm run typecheck`, `npm test`, and `npm run build` —
  passed; three graph projection tests passed.
- `python -m ruff format --check .` — passed, 134 files already formatted.
- `python -m ruff check .` and `python -m mypy hawkeye` — passed.
- `python -m pytest -q --durations=10` — 190 passed in 512.95 seconds; one upstream
  FastAPI/Starlette deprecation warning.
- Browser QA at 1440×900 — passed: 15 saved entries loaded; landing and report remained vertically
  scrollable with zero horizontal overflow; the saved QQ workspace displayed one interactive
  canvas, 11 nodes/12 links, 23 evidence cards, real persisted timeline events, and the full-page
  screenshot by default. Graph filtering, evidence expansion, and the ten-section summary worked
  without console warnings/errors. Duplicate local browser tabs were closed.
- Lazy chunks are served through a bounded local JavaScript filename route. Missing/traversal-like
  chunk paths remain 404 and are regression-tested.

## Implemented product boundary

- Canonical collection always uses 0/500/1500/3000 ms checkpoints, may extend observation to
  5000/8000 ms for an information-rich changing page, and performs one fixed read-only
  middle/bottom/top sweep on scrollable pages before the final canonical checkpoint.
- Capture access, adequacy, extraction eligibility, and public status are separate fields.
- New capture artifacts are hash/size/type verified by the legacy local loader.
- Semantic observations are public observables, not assertions; crop generation is best effort.
- Judol indicators are versioned deterministic observation classifications. They are counted as
  integers with page/artifact/screenshot references; they are not percentages, probabilities,
  legality labels, ownership claims, or absence claims.
- Live UI scans expose real collector/agent/classifier/graph stages through one recoverable local
  job. Playwright runs in a spawned process with a final 115-second browser wall-clock stop.
- Interaction tools use snapshot-bound references in a maximum-five-decision/three-interaction
  objective loop with explicit stale/no-op/budget stop reasons.
- The current codex-lb probe discovers `gpt-5.6-terra` and verifies strict structured output. The
  final QQ validation used Codex; transport/schema/reference failure remains a logged fallback.
- Synthetic recollection and live direct-link recollection are implemented. A live candidate is
  collected once only after `candidate_page.approved`; generated candidates are never auto-crawled.
- Assertions and reviews are append-only; current review status is derived from history.
- Exact cross-case public identifiers may create pending assertions with both artifact chains;
  same-host captures retain an added/removed/unchanged temporal comparison.
- Graph truth is reduced from persisted events; canvas force motion, particles, minimap, and replay
  never create graph truth. The canvas excludes diagnostic artifact nodes; initial/canonical/full
  screenshots and artifacts remain in the inspector.
- The official benchmark is synthetic and measures observable/task/policy behavior only.

## Known limitations and human-owned completion

- The 12 live observations vary by geography, VPN exit, challenge, session, and time; they remain
  ignored local artifacts and are not test truth.
- The final owner-authorized QQ validation captured two same-site pages, 11 provisional seed/crawl
  observations, a Codex-selected `/Contact` action, three artifact-backed public-contact channels,
  and one approval-gated `qq101uok.com` lead. The Indonesian and English contact variants differ;
  the interaction capture declares `id-ID` and records that locale-sensitive result.
- Chromium DNS validation retains the documented TOCTOU residual risk.
- Capture thresholds and interaction coverage are calibrated only on controlled fixtures.
- Local OCR is optional and currently unavailable on this machine because Tesseract is not
  installed; OCR-derived signals would remain provisional. No universal live-web safety guarantee,
  ownership probability, operator identification, criminality, or legal conclusion is claimed.
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
- `6364351` — contact-route evidence extraction, graph taxonomy/aggregation, and core 888 lead
  priority.

The package/final-status commit is recorded in the delivery handoff. Nothing is pushed or deployed.
