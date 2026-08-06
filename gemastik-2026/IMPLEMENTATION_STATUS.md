# Implementation Status

Allowed status vocabulary: implemented, partially implemented, planned, deferred.

| Capability | Status | Repository path | Test | Demo step | Limitation |
|---|---|---|---|---|---|
| Four independent capture dimensions | implemented | `hawkeye/models.py`, `hawkeye/pipeline.py` | `tests/test_capture_adequacy.py` | Inspect run capture status/readiness | Old cases may not contain new optional fields |
| Mandatory checkpoints plus bounded 5000/8000 ms settle extension | implemented | `hawkeye/collector/playwright_collector.py` | `tests/test_capture_adequacy.py` | Delayed/dynamic fixtures | Eight seconds may still miss later rendering |
| Visible text and visual-information metrics | implemented | `hawkeye/collector/playwright_collector.py` | capture adequacy tests | Read readiness JSON | Thresholds calibrated only on controlled fixtures |
| HTML 2 MB extraction / 5 MB persistence policy | implemented | `hawkeye/pipeline.py`, `hawkeye/collector/playwright_collector.py` | oversize capture tests | Inspect oversize fixture artifacts | Above 5 MB HTML is intentionally omitted |
| Initial/final/bounded full-page artifacts | implemented | `hawkeye/storage/filesystem.py` | capture adequacy tests | Open evidence inventory | Full page capped at 12,000 px |
| Fifteen semantic observation types | implemented | `hawkeye/semantic_evidence.py` | `tests/test_semantic_evidence.py` | Evidence inspector | DOM remains primary |
| Bounded optional screenshot OCR | implemented | `hawkeye/ocr.py`, case pipeline/storage | `tests/test_ocr.py`, UI capture test | OCR metadata artifact | Tesseract is not installed on the verification machine; derived evidence is provisional |
| Evidence crops | implemented | `hawkeye/pipeline.py` | semantic evidence test | Open crop in collected case | Best-effort only for stable viewport boxes |
| Exactly ten interaction scenarios | implemented | `evaluation/fixtures/controlled-interactions-v1.json` | `tests/test_controlled_interaction.py` | Seed selector | Fixture scope only |
| Multi-step snapshot-bound objective loop | implemented | `hawkeye/agent/loop.py`, interaction/runtime modules | stale/no-op/two-step benchmark tests | Per-step graph timeline | Maximum five decisions and three interactions; not unrestricted computer use |
| Bounded scroll/shadow/frame discovery | implemented | collector and crawl pipeline | crawl/capture tests | Frontier provenance | Open shadow roots and same-origin frames only; browser isolation is not bypassed |
| Server-side unsafe-action policy | implemented | `hawkeye/interaction/policy.py` | policy/benchmark tests | Policy safety table | Cannot prove universal live-web safety |
| codex-lb capability probe | implemented | `hawkeye/agent/capability.py` | `tests/test_agent_runtime.py` | Show capability JSON | Fixed loopback routes only; native search unused |
| Structured Codex decision validation | implemented | `hawkeye/agent/investigator.py` | invalid-schema/reference tests | QQ Codex timeline | Model path depends on a successful local strict-output probe |
| Deterministic fallback | implemented | `hawkeye/agent/investigator.py` | agent/runtime/benchmark tests | Canonical demo banner | Rule selection is intentionally simple |
| Direct/redirect/new-tab/iframe discovery | implemented | controlled fixture/runtime modules | interaction/runtime tests | Canonical redirect scenario | Native/paid search excluded |
| Synthetic fixture index search | implemented | `hawkeye/investigation/runtime.py` | runtime tests | Page B recollection | Reserved `.invalid` fixtures only |
| Page B approval boundary | implemented | runtime/workspace modules | approval-gated UI/API and live graph tests | Approval → one-page Page B | Only directly observed candidates; no automatic generated-candidate crawl |
| Cross-case exact matching and temporal diff | implemented | live runtime/store/UI projection | runtime exact-contact/temporal test | Shared contact pending assertion | Exact identifiers only; evidence match is not ownership |
| Evidence-backed candidate assertions | implemented | investigation models/store/runtime | runtime tests | Assertion panel | Relationship support only, never ownership |
| Append-only SQLite reviews | implemented | `hawkeye/investigation/store.py` | review-history tests | Append review | Single-machine label, no authenticated identity |
| Append-only event log | implemented | `hawkeye/investigation/store.py` | event tests | Timeline | Local SQLite only |
| Idempotent progressive graph | implemented | `hawkeye/investigation/reducer.py` | replay test | Canvas replay/refresh | Persistent truth remains independent of canvas state |
| Three-view start/workspace/summary console | implemented | review app static assets and export API | Node syntax, UI/API/export tests, browser QA | Recent case → graph → summary | Localhost-only, dependency-free vanilla JS |
| Screenshot carousel/timeline/search/review | implemented | review app static assets/workspace API | `tests/test_mvp_workspace_ui.py`, browser QA | Local UI | Initial/canonical/full-page views depend on capture availability |
| Reduced-motion mode | implemented | review app static assets | frontend syntax/UI API gate | OS reduced-motion setting | Motion is removed; graph information remains |
| Three-mode benchmark | implemented | `hawkeye/benchmark.py`, checked-in results | `tests/test_benchmark.py` | Benchmark table | Runtime rounds to milliseconds; fast runs can show 0 ms |
| Optional live robustness observations | implemented | ignored `evaluation/live-cases/` output | 12-target matrix plus final QQ run | Local QQ default only | QQ produced provisional evidence; live output is never official test truth |
| Public deployment/authentication | deferred | none | none | none | Requires separate threat model and authorization milestone |
| Final proposal PDF | deferred | Markdown package | checklist | none | Human confirmations and layout review required |
| Actual final screenshots | implemented | `gemastik-2026/assets/` | final demo/browser gate | six sanitized fixture figures | Video recording and document-layout diagrams remain human-owned |

## Current exact verification

Verified on 2026-08-03 (Asia/Jakarta): Ruff format checked 122 files; Ruff lint passed; strict mypy
passed for 60 source files; JavaScript syntax passed; pytest passed all 176 tests in 470.26 seconds
with one upstream FastAPI/Starlette deprecation warning; and `git diff --check` passed. A fresh
ten-fixture/three-mode benchmark completed with 30 deterministic-fallback
agent attempts and a 1.0 unsafe-action block rate. A fresh sanitized legacy CLI demo completed.

Browser QA opened the latest QQ run as the local default with two captured same-site pages, three
seed screenshot views, 11 provisional seed/crawl semantic observations, a completed real
Codex-selected `/Contact` action, three contact-channel observations backed by the interaction
screenshot/HTML/text/JSON, a direct candidate waiting for approval, and an 11-node/10-link graph.
Official figures use only
sanitized fixtures: scenario 6 collapses equal URL identities, recollects Page B, displays a dashed
two-observation assertion, and changes only that assertion to `solid_emphasized` after append-only
review; scenario 8 persists two policy-preflight blocks with `executed=false`. Six current
screenshots and hashes are recorded in `FIGURE_INDEX.md`.

The coherent G4A–G9 implementation and current canvas are committed as `67a039b`; contact evidence
and compact graph semantics are committed as `6364351`. Earlier bounded
milestone commits remain intact, and the final package commit is reported in the repository
handoff. No commit was pushed.
