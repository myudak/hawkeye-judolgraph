# Implementation Status

Allowed status vocabulary: implemented, partially implemented, planned, deferred.

| Capability | Status | Repository path | Test | Demo step | Limitation |
|---|---|---|---|---|---|
| Four independent capture dimensions | implemented | `apps/api/src/hawkeye/models.py`, `apps/api/src/hawkeye/pipeline.py` | `tests/test_capture_adequacy.py` | Inspect run capture status/readiness | Old cases may not contain new optional fields |
| Mandatory checkpoints plus bounded 5000/8000 ms settle extension | implemented | `apps/api/src/hawkeye/collector/playwright_collector.py` | `tests/test_capture_adequacy.py` | Delayed/dynamic fixtures | Eight seconds may still miss later rendering |
| Visible text and visual-information metrics | implemented | `apps/api/src/hawkeye/collector/playwright_collector.py` | capture adequacy tests | Read readiness JSON | Thresholds calibrated only on controlled fixtures |
| HTML 2 MB extraction / 5 MB persistence policy | implemented | `apps/api/src/hawkeye/pipeline.py`, collector | oversize capture tests | Inspect oversize fixture artifacts | Above 5 MB HTML is intentionally omitted |
| Initial/final/bounded full-page artifacts | implemented | `apps/api/src/hawkeye/storage/filesystem.py` | capture adequacy tests | Open evidence inventory | Full page capped at 12,000 px |
| Fifteen semantic observation types | implemented | `apps/api/src/hawkeye/semantic_evidence.py` | `tests/test_semantic_evidence.py` | Evidence inspector | DOM remains primary |
| Explainable count-based judol indicators | implemented | `apps/api/src/hawkeye/indicators.py`, review loader/UI | `tests/test_indicators.py` | Recent case → evidence → summary | Integer evidence count only; not percentage, probability, legality, or ownership |
| Bounded optional screenshot OCR | implemented | `apps/api/src/hawkeye/ocr.py`, case pipeline/storage | `tests/test_ocr.py`, UI capture test | OCR metadata artifact | Tesseract availability depends on local install; Docker image includes it |
| Evidence crops | implemented | `apps/api/src/hawkeye/pipeline.py` | semantic evidence test | Open crop in collected case | Best-effort only for stable viewport boxes |
| Exactly ten interaction scenarios | implemented | `evaluation/fixtures/controlled-interactions-v1.json` | `tests/test_controlled_interaction.py` | Seed selector | Fixture scope only |
| Multi-step snapshot-bound objective loop | implemented | `apps/api/src/hawkeye/agent/loop.py`, interaction/runtime modules | stale/no-op/two-step benchmark tests | Per-step graph timeline | Maximum five decisions and three interactions; not unrestricted computer use |
| Bounded scroll/shadow/frame discovery | implemented | collector and crawl pipeline | crawl/capture tests | Frontier provenance | Open shadow roots and same-origin frames only; browser isolation is not bypassed |
| Server-side unsafe-action policy | implemented | `apps/api/src/hawkeye/interaction/policy.py` | policy/benchmark tests | Policy safety table | Cannot prove universal live-web safety |
| Generic OpenAI-compatible adapter | implemented | `apps/api/src/hawkeye/agent/` | `tests/test_agent_runtime.py`, `tests/test_llm_provider.py` | Optional explicit `llm-probe` | No automatic paid probe; model remains optional |
| Structured model decision validation | implemented | `apps/api/src/hawkeye/agent/investigator.py` | invalid-schema/reference/transport tests | Historical QQ model timeline | New model runs depend on operator environment; failures fall back |
| Deterministic fallback | implemented | `apps/api/src/hawkeye/agent/investigator.py` | agent/runtime/benchmark tests | Canonical demo banner | Rule selection is intentionally simple |
| Direct/redirect/new-tab/iframe discovery | implemented | controlled fixture/runtime modules | interaction/runtime tests | Canonical redirect scenario | Native/paid search excluded |
| Synthetic fixture index search | implemented | `apps/api/src/hawkeye/investigation/runtime.py` | runtime tests | Page B recollection | Reserved `.invalid` fixtures only |
| Page B approval boundary | implemented | runtime/workspace modules | approval-gated UI/API and live graph tests | Approval → one-page Page B | Only directly observed candidates; no automatic generated-candidate crawl |
| Cross-case exact matching and temporal diff | implemented | live runtime/store/UI projection | runtime exact-contact/temporal test | Shared contact pending assertion | Exact identifiers only; evidence match is not ownership |
| Evidence-backed candidate assertions | implemented | investigation models/store/runtime | runtime tests | Assertion panel | Relationship support only, never ownership |
| Append-only SQLite reviews | implemented | `apps/api/src/hawkeye/investigation/store.py` | review-history tests | Append review | Single-machine label, no authenticated identity |
| Append-only event log | implemented | `apps/api/src/hawkeye/investigation/store.py` | event tests | Timeline | Local SQLite only |
| Idempotent progressive graph | implemented | `apps/api/src/hawkeye/investigation/reducer.py` | replay test | Canvas replay/refresh | Persistent truth remains independent of canvas state |
| Three-view start/workspace/summary console | implemented | review app static assets and export API | Node syntax, UI/API/export tests, browser QA | Recent case → graph → summary | Localhost-only, dependency-free vanilla JS |
| Screenshot carousel/timeline/search/review | implemented | review app static assets/workspace API | `tests/test_mvp_workspace_ui.py`, browser QA | Local UI | Initial/canonical/full-page views depend on capture availability |
| Recoverable progressive scan jobs and browser hard stop | implemented | `apps/api/src/hawkeye/review_app/` | `tests/test_investigation_jobs.py`, progressive UI API test | Start guided scan and observe named stages | One active localhost job; browser capture hard-stops at 115 seconds |
| Animated truthful scan instrumentation | implemented | review app static assets | Node syntax, reduced-motion, browser QA | Observe orbit/stage/history/elapsed states | No fabricated percentage; motion follows backend stage snapshots |
| Reduced-motion mode | implemented | review app static assets | frontend syntax/UI API gate | OS reduced-motion setting | Motion is removed; graph information remains |
| Three-mode benchmark | implemented | `apps/api/src/hawkeye/benchmark.py`, checked-in results | `tests/test_benchmark.py` | Benchmark table | Runtime rounds to milliseconds; fast runs can show 0 ms |
| Apps monorepo + locked package workflows | implemented | `apps/api`, `apps/web`, `uv.lock`, `pnpm-lock.yaml` | root check/package commands | Build wheel and inspect assets | Browser/Docker downloads still require stable connectivity |
| Local one-service Docker boundary | implemented | `Dockerfile`, `compose.yaml`, `infra/docker/seccomp_profile.json` | `pnpm verify:docker`: non-root, sandboxed capture/OCR, hard-timeout cleanup, persistence | `docker compose up --build` | Local single-investigator only; no public deployment/authentication |
| Optional live robustness observations | implemented | ignored `evaluation/live-cases/` output | 12-target matrix plus final QQ run | Local QQ default only | QQ produced provisional evidence; live output is never official test truth |
| Public deployment/authentication | deferred | none | none | none | Requires separate threat model and authorization milestone |
| Final proposal PDF | deferred | Markdown package | checklist | none | Human confirmations and layout review required |
| Actual final screenshots | implemented | `gemastik-2026/assets/` | final demo/browser gate | six sanitized fixture figures | Video recording and document-layout diagrams remain human-owned |

## Current exact verification

Verified on 2026-08-11 (Asia/Jakarta): root frozen pnpm/uv installs passed; Prettier, ESLint,
TypeScript, five Vitest tests, and the production React build passed; Ruff format checked 146 files,
Ruff lint passed, strict mypy passed for 69 source files, and all 203 pytest tests passed in 522.72
seconds with one upstream FastAPI/Starlette deprecation warning. An isolated wheel install loaded
the packaged UI and all ten controlled fixtures. `pnpm verify:manual` passed
loopback health/landing/fallback isolation. `pnpm verify:docker` passed a real canonical fixture
capture with Tesseract OCR, non-root UID, Chromium sandbox, pinned seccomp, minimal capability,
hard-timeout child cleanup, loopback-only publishing, and restart persistence. `pnpm package` built
the complete UI-bearing wheel. No live URL or credential is automated test truth.

Verified on 2026-08-08 (Asia/Jakarta): Ruff format checked 132 files; Ruff lint passed; strict mypy
passed for 65 source files; JavaScript syntax passed; pytest passed all 190 tests in 470.26 seconds
with one upstream FastAPI/Starlette deprecation warning; and `git diff --check` passed. A fresh
ten-fixture/three-mode benchmark completed with 30 deterministic-fallback
agent attempts and a 1.0 unsafe-action block rate. A fresh sanitized legacy CLI demo completed.

Browser QA opened a verified QQ Codex run with two captured same-site pages, full-page screenshot
as the default evidence view, 20 semantic observations, six counted judol indicators, one safe
stored agent action, and an 11-node/12-link event graph. The verified 888 run displayed 25 indicators
and a 26-node/25-link graph with public links to `888casino.com`, `888poker.com`, and `888sport.com`.
The start/workspace/summary views had no horizontal overflow or browser console errors. A fresh
owner-authorized QQ guided validation remained in page capture under the current network; the new
hard boundary terminated its browser process at 115 seconds and the UI changed from live stage
instrumentation to an explicit stopped reason instead of hanging.
Official figures use only
sanitized fixtures: scenario 6 collapses equal URL identities, recollects Page B, displays a dashed
two-observation assertion, and changes only that assertion to `solid_emphasized` after append-only
review; scenario 8 persists two policy-preflight blocks with `executed=false`. Six current
screenshots and hashes are recorded in `FIGURE_INDEX.md`.

The coherent G4A–G9 implementation and current canvas are committed as `67a039b`; contact evidence
and compact graph semantics are committed as `6364351`. Earlier bounded
milestone commits remain intact, and the final package commit is reported in the repository
handoff. No commit was pushed.
