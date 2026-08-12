# Project Status

## Current milestone

**G4A–G9 — GEMASTIK preliminary MVP plus post-G9 investigator hardening** is implemented and locally verified. The product now combines
capture adequacy, optional bounded OCR, ten controlled safe-expansion scenarios, an optional
OpenAI-compatible model path with deterministic fallback, approval-gated live candidate recollection,
exact cross-case assertions, temporal diffs, append-only human review, a WebGraph-informed 2D canvas
over event-reduced truth, explainable integer judol-indicator counts, recoverable progressive scan
jobs with a killable browser boundary, a three-mode benchmark, one bounded
12-target live robustness matrix, and a truthful Markdown submission package. G2/G3 tags and
commits remain unchanged.

## Delivery and monorepo verification snapshot

Verified on 2026-08-11 (Asia/Jakarta) from branch
`codex/gemastik-preliminary-mvp-48d4`:

- Source is organized as `apps/api/src/hawkeye` plus `apps/web`; root tests/evaluation retain their
  historical node IDs and fixture paths. Generated Vite assets, wheels, local data, captures,
  SQLite workspaces, and document exports are ignored rather than tracked source.
- `pnpm install --frozen-lockfile` and `uv sync --locked --extra dev` passed from the shared root
  manifests. `pnpm verify:manual` built the production UI, started an isolated loopback FastAPI
  process, verified `/health` and landing delivery, confirmed `fallback_only` with no credentials,
  and removed its temporary data/process tree.
- Root gates passed: Prettier, ESLint, TypeScript, five Vitest projection tests, production Vite
  build, Ruff format/check across 146 Python files, strict mypy across 69 source files, the final
  203-test pytest suite in 522.72 seconds, and `git diff --check`. The only warning is the upstream
  FastAPI/Starlette `httpx` test-client deprecation.
- Generic provider fixtures passed Responses strict output, Chat Completions strict output,
  `404/405`-only auto-switch, timeout, redirect denial, response-size bound, exact schema/reference
  validation, environment aliases for a local compatible gateway, no-probe capability reporting,
  and secret exclusion. No live credential is stored or required; deterministic fallback remains
  the credential-free default.
- `pnpm verify:docker` built the pinned image and passed a real canonical fixture capture with local
  Tesseract OCR, non-root UID 1001, Chromium sandbox, pinned seccomp, read-only root filesystem,
  all capabilities dropped except `SYS_CHROOT`, hard-timeout Chromium-child cleanup, host-loopback
  port publishing, `/health`, and data persistence across Compose `down/up`.
- `pnpm package` built a wheel containing the Python runtime, CLI, controlled fixture manifest, and
  complete generated React UI. An installed-wheel locator regression is included in the final 203,
  and an isolated no-project install loaded the UI plus all ten fixture scenarios from
  `site-packages`. Container and manual acceptance use temporary data roots and leave no test
  container or case in canonical project data.

## Historical product verification snapshots

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

Graph V2 interaction refresh verified on 2026-08-10 (Asia/Jakarta):

- The canvas now uses a central investigated-site node, density-aware semantic orbits, vector
  category icons, contextual edge labels, one-hop focus, and Evidence/Navigation/Review lenses.
- The right inspector defaults to direct category summaries; the left and right panels collapse
  independently; the footer status strip was removed; the event replay bar separates transport,
  current event, trail, and scrubber; workspace presentation copy toggles between English and
  Indonesian without rewriting persisted values.
- Frontend formatting, lint, TypeScript, five graph tests, and production build passed. Browser QA
  passed on the saved 11-node QQ investigation and dense 26-node 888 investigation. The Review
  lens reduced QQ to the seed plus one pending candidate, both panels collapsed into full-canvas
  mode, and the simplified inspector exposed clickable brand/contact/link/payment/offer groups.

Progressive evidence-preview refresh implemented on 2026-08-10 (Asia/Jakarta):

- Canonical screenshots enter the active job only after persistence and change from transient to
  verified only after the completed case reload succeeds. Preview delivery rechecks the recorded
  SHA-256, PNG header, and exact dimensions; verified canonical frames also pass the manifest-backed
  artifact loader.
- Policy-gated interactions persist a before frame with the real revalidated element bounding box,
  then a separate result frame. The result is not projected as completed until screenshot/state/
  HTML/text artifacts and the append-only `tool.completed` event exist. A failed action is shown as
  stopped rather than completed.
- The React scan view is screenshot-first, provides bounded before/after thumbnails, uses shimmer
  and scanline motion only while the job is active, freezes terminal elapsed time, and reports zero
  newly extracted observations truthfully. It still uses real stage names rather than percentages.
- `python -m ruff format --check .`, `python -m ruff check .`, and
  `python -m mypy hawkeye` passed. `python -m pytest -q --durations=10` passed 191 tests in
  543.42 seconds with one upstream FastAPI/Starlette deprecation warning.
- Frontend formatting, ESLint, TypeScript, five projection tests, and production build passed. The
  lazy landing chunk is 33.79 kB (10.21 kB gzip), the scan chunk is 40.99 kB (12.15 kB gzip), and
  supplied brand images are served as fixed same-origin assets rather than base64 JavaScript.
- Local browser QA verified the Indonesian landing, larger case cards, language switch, active scan
  radar, real stage/elapsed reporting, and the explicit terminal failure state. The live QQ check
  reached the 115-second browser wall before a valid frame was preserved; the UI froze at 01:56,
  marked the capture/stage/activity as stopped, and did not fabricate a screenshot or completion.

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
- The current runtime accepts an operator-configured OpenAI-compatible provider and performs no
  automatic probe. The final 2026-08-03 QQ validation used Codex historically;
  transport/schema/reference failure remains a logged deterministic fallback.
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
- Local OCR is optional and unavailable on the manual Windows path unless Tesseract is installed;
  the verified Docker image includes Tesseract. OCR-derived signals remain provisional. No
  universal live-web safety guarantee, ownership probability, operator identification, criminality,
  or legal conclusion is claimed.
- The console remains localhost-only and single-machine. An optional environment-configured HTTP
  Basic gate protects every UI/API/artifact route except `/health`; review labels remain audit text,
  not authenticated user identities.
- An owner-authorized temporary demo configuration admits only exact Host/Origin
  `hawkeye.myudak.com` through an external TLS tunnel while Compose remains bound to host loopback.
  Basic Auth is optional; without it this is explicitly an unauthenticated demo, not a production
  deployment or identity boundary.
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
- `d34f275` — source monorepo move, shared lockfiles, generic provider adapter, and initial
  container/package boundary.

## Windows distribution verification — 2026-08-12

- The native Windows `onedir` bundle and non-elevated Inno Setup installer were rebuilt from the
  locked monorepo with the generated React application and Playwright Chromium included.
- Repository gates passed: Prettier, ESLint, TypeScript, five frontend projection tests, Vite
  production build, Ruff format/check, mypy over 73 source files, 232 backend tests, and Astro
  diagnostics for the presentation site. The upstream FastAPI/Starlette deprecation warning remains.
- The frozen executable passed its spawn, `tldextract` snapshot, bundled-Chromium, health, and React
  landing self-tests. A silent installer round trip then installed the application, repeated the
  same smoke test, and uninstalled it successfully.
- Final local assets: `HAWK-EYE-1.0.0-windows-x64-portable.zip` (308,685,926 bytes; SHA-256
  `527d433f47358187621aa7614d581899c67337137dfa4dac75a8463b0b39cfaf`) and
  `HAWK-EYE-Setup-1.0.0-windows-x64.exe` (220,790,396 bytes; SHA-256
  `79a9a37e9338be522314286e81d1555c6d9f0003e20619f7929bf19117cc224f`).
- The desktop settings surface can enable/disable an OpenAI-compatible provider, retain or remove a
  locally stored key, and apply a validated configuration to new investigations without a paid
  probe. API secrets are not returned in normal or oversized-input validation responses.
- The current Windows assets are unsigned. They are suitable for a transparent competition preview;
  a generally distributed production build still requires code signing and completion of the
  dependency redistribution review.

The package/final-status commit is recorded in the delivery handoff. Generated release assets remain
ignored and are published only through the tagged GitHub release workflow.
