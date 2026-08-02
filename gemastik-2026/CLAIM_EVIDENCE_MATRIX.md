# Claim–Evidence Matrix

| Proposed claim | Evidence source | Test/measurement | Safe wording | Prohibited extrapolation |
|---|---|---|---|---|
| Blank-first pages are not captured at 0 ms | readiness checkpoints and delayed fixture | `test_delayed_render_uses_final_canonical_state_and_preserves_initial` | Canonical fixture state is selected at 3000 ms | All live pages are complete by 3000 ms |
| Hidden DOM cannot fake visible evidence | browser `innerText`, visibility and pixels | rich-hidden blank case | Hidden fixture DOM is extraction-ineligible | Hidden content never influences a live browser |
| Access and adequacy are independent | case/page models | capture dimension parametrized test | Geo/challenge/unavailable labels are separate from adequacy | Cause, legality, or bypassability of restriction |
| Oversize HTML preserves partial evidence | readiness, visible text, screenshots, metadata | 2–5 MB and >5 MB tests | Oversize fixture remains captured with explicit omission | Full HTML exists above the persistence limit |
| Semantic observations retain provenance | `observations.json` and crops | semantic evidence tests | Required observation classes have artifact/screenshot provenance | Extracted value proves ownership |
| Unsafe controlled actions are blocked | policy decisions and raw benchmark | 12/12 approach-policy probes over four unique prohibited controls | 100% controlled fixture block rate | Universal live-site safety guarantee |
| Exactly ten scenarios are authoritative | controlled fixture JSON | fixture manifest test | Initial benchmark uses ten stable scenarios | Dataset represents the entire web |
| Model-free operation works | agent fallback events | agent/runtime/benchmark tests | Deterministic fallback completed controlled tasks | Live Codex produced the result |
| `/v1/responses` route exists locally | capability diagnostics v2 | actual bounded 400 response | Route present; required capabilities unknown | Model/tool/native-search support exists |
| Page B is recollected before assertion | Page A/B artifacts and event order | runtime flow test | Synthetic assertion follows Page B artifact and observation | Real candidate is already verified |
| Real candidates require approval | approval-required event | real-mode test/UI API test | Real mode stops before Page B collection | Approval performs or guarantees collection |
| Reviews are append-only | SQLite rows/triggers | review history/update rejection test | Review versions are immutable local events | Reviewer identity is authenticated |
| Graph is event-derived and replayable | event log/reducer | duplicate replay consistency test | Duplicate event replay yields same graph state | Animation proves an event occurred |
| Static recall is 0.2857 | raw benchmark JSON | 10 static attempts | Controlled observable recall | Real-world recall |
| Rule/agent recall is 1.0000 | raw benchmark JSON | 10 rule + 30 deterministic-agent attempts | Controlled observable recall | Model accuracy or live accuracy |
| Provenance completeness is 1.0000 | raw benchmark JSON | measured normalized fixture outputs | Controlled attempt provenance completeness | Every future artifact is complete |
| Agent attempts are stable | nondeterminism table | three attempts per scenario | One signature per controlled scenario | Any stochastic model would be deterministic |

## Human-owned claims not yet supported

- Final product name and brand originality.
- Team roles, institution, advisor, and signatures.
- Interviews, usability participants, adoption, impact, or sustainability metrics.
- Public deployment history.
- Official rules/page-count compliance.
- External novelty comparison, legal characterization, or jurisdictional claims.
- Dependency license clearance for redistribution.

