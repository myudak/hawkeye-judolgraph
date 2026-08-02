# Implementation Status

Allowed status vocabulary: implemented, partially implemented, planned, deferred.

| Capability | Status | Repository path | Test | Demo step | Limitation |
|---|---|---|---|---|---|
| Four independent capture dimensions | implemented | `hawkeye/models.py`, `hawkeye/pipeline.py` | `tests/test_capture_adequacy.py` | Inspect run capture status/readiness | Old cases may not contain new optional fields |
| Fixed 0/500/1500/3000 ms canonical capture | implemented | `hawkeye/collector/playwright_collector.py` | `tests/test_capture_adequacy.py` | Delayed-render fixture | Fixed budget may still miss later rendering |
| Visible text and visual-information metrics | implemented | `hawkeye/collector/playwright_collector.py` | capture adequacy tests | Read readiness JSON | Thresholds calibrated only on controlled fixtures |
| HTML 2 MB extraction / 5 MB persistence policy | implemented | `hawkeye/pipeline.py`, `hawkeye/collector/playwright_collector.py` | oversize capture tests | Inspect oversize fixture artifacts | Above 5 MB HTML is intentionally omitted |
| Initial/final/bounded full-page artifacts | implemented | `hawkeye/storage/filesystem.py` | capture adequacy tests | Open evidence inventory | Full page capped at 12,000 px |
| Fourteen semantic observation types | implemented | `hawkeye/semantic_evidence.py` | `tests/test_semantic_evidence.py` | Evidence inspector | Text/DOM primary; no image OCR claim |
| Evidence crops | implemented | `hawkeye/pipeline.py` | semantic evidence test | Open crop in collected case | Best-effort only for stable viewport boxes |
| Exactly ten interaction scenarios | implemented | `evaluation/fixtures/controlled-interactions-v1.json` | `tests/test_controlled_interaction.py` | Seed selector | Fixture scope only |
| Stable snapshot-bound references | implemented | `hawkeye/interaction/` | stale-reference test | Timeline/tool payload | Controlled executor, not unrestricted real Playwright |
| Server-side unsafe-action policy | implemented | `hawkeye/interaction/policy.py` | policy/benchmark tests | Policy safety table | Cannot prove universal live-web safety |
| codex-lb capability probe | implemented | `hawkeye/agent/capability.py` | `tests/test_agent_runtime.py` | Show capability JSON | Current route does not advertise required model capabilities |
| Structured Codex decision validation | implemented | `hawkeye/agent/investigator.py` | invalid-schema tests | Agent timeline | Live model path disabled by capability result |
| Deterministic fallback | implemented | `hawkeye/agent/investigator.py` | agent/runtime/benchmark tests | Canonical demo banner | Rule selection is intentionally simple |
| Direct/redirect/new-tab/iframe discovery | implemented | controlled fixture/runtime modules | interaction/runtime tests | Canonical redirect scenario | Native/paid search excluded |
| Synthetic fixture index search | implemented | `hawkeye/investigation/runtime.py` | runtime tests | Page B recollection | Reserved `.invalid` fixtures only |
| Page B approval boundary | partially implemented | runtime/workspace modules | approval-gated UI/API test | Approval → controlled Page B | Reserved fixture recollection completes only after approval; external recollection is deliberately disabled |
| Evidence-backed candidate assertions | implemented | investigation models/store/runtime | runtime tests | Assertion panel | Relationship support only, never ownership |
| Append-only SQLite reviews | implemented | `hawkeye/investigation/store.py` | review-history tests | Append review | Single-machine label, no authenticated identity |
| Append-only event log | implemented | `hawkeye/investigation/store.py` | event tests | Timeline | Local SQLite only |
| Idempotent progressive graph | implemented | `hawkeye/investigation/reducer.py` | replay test | Canvas replay/refresh | Persistent truth remains independent of canvas state |
| Canvas graph/pan/zoom/drag/hit-test/minimap | implemented | review app static assets | Node syntax, static safety, browser QA | Saved QQ and fixture run | Dependency-free vanilla JS; no 3D layouts |
| Screenshot inspector/timeline/search/review | implemented | review app static assets/workspace API | `tests/test_mvp_workspace_ui.py`, browser QA | Local UI | Alternate screenshot views stay in artifact inventory |
| Reduced-motion mode | implemented | review app static assets | frontend syntax/UI API gate | OS reduced-motion setting | Motion is removed; graph information remains |
| Three-mode benchmark | implemented | `hawkeye/benchmark.py`, checked-in results | `tests/test_benchmark.py` | Benchmark table | Runtime rounds to milliseconds; fast runs can show 0 ms |
| Optional live robustness observations | implemented | ignored `evaluation/live-cases/` output | 12-target one-run matrix | Local QQ default only | 11 navigation captures; no live extraction eligible; never official test truth |
| Public deployment/authentication | deferred | none | none | none | Requires separate threat model and authorization milestone |
| Final proposal PDF | deferred | Markdown package | checklist | none | Human confirmations and layout review required |
| Actual final screenshots | planned | `gemastik-2026/assets/` | final demo gate | sanitized fixture UI | Captured only after final full gate; video remains human-owned |

## Current exact verification

Verified on 2026-08-03 (Asia/Jakarta): Ruff format and lint passed; strict mypy passed for 59 source
files; JavaScript syntax passed; pytest passed all 158 tests in 380.88 seconds; and `git diff
--check` passed. A fresh ten-fixture/three-mode benchmark completed with 30 deterministic-fallback
agent attempts and a 1.0 unsafe-action block rate. A fresh sanitized legacy CLI demo completed.

The localhost UI walkthrough ran controlled scenario 6, recollected fixture Page B, displayed a
dashed two-observation assertion, appended review version 0 → 1, and replayed 18 monotonic events to
a `solid_emphasized` edge. The walkthrough used only reserved `.invalid` data and ignored local
artifacts under `verification-output/`.

Implementation commits: `ad6b917`, `cf648e8`, and compatibility commit `4944659`. The final package
commit is reported in the repository handoff; no commit was pushed.
