# JudolGraph / HAWK-EYE Roadmap

This roadmap records boundaries, not promises. A future milestone begins only after its scope and
acceptance criteria are documented and reviewed.

## Verified baseline — completed

- **V0 — Seed to Evidence Graph:** safe public URL validation, bounded Playwright collection,
  HTML/screenshot preservation, deterministic extraction, and an evidence-backed graph.
- **V0.1 — Bounded same-site crawl:** depth `0..1`, at most five HTML pages, with evidence-backed
  frontier decisions.
- **V0.2 — Candidate generation:** deterministic, evidence-backed `pending` candidates with
  local-corpus signal controls.
- **V0.3 — Offline comparison:** artifact-verified, explainable component scores with
  `needs_review` semantics.
- **V0.4 — External discovery:** one opt-in, bounded URLScan public-record adapter that never
  opens returned candidates.
- **V1 — Local investigator console:** verified local cases only, strict headers, safe artifact
  delivery, Host-header protection, and no public bind.

Baseline tag: `v1.0.0-baseline`.

## G0 — Governance and reproducible evaluation baseline — completed

Acceptance boundary:

- Permanent project rules and decision records exist.
- Local deterministic evaluation fixtures and expected properties exist.
- Two user-supplied public URLs are registered as opt-in live manifests, not CI truth.
- A read-only report can verify a completed local case against manifest invariants.
- Chrome observations remain separate qualitative notes; any bug becomes a fixture-backed future
  milestone.

Completed evidence: baseline tag `v1.0.0-baseline`, operational governance documents, two opt-in
public manifests, a verified fixture-policy hash, a fully local delayed-render shell fixture,
read-only `hawkeye evaluate` reports, and 103 passing automated tests.

## G1 — Rendered-content completeness diagnostics and bounded capture-readiness evaluation — completed

Potential work: define reproducible completeness indicators and bounded render-readiness timing
budgets for sparse initial shells that later render client-side. It must not introduce CAPTCHA
bypass, stealth plugins, unrestricted delays, arbitrary user-agent impersonation, or interaction
with login controls.

Completed evidence: an opt-in `hawkeye diagnose` command; immutable in-case diagnostics; fixed
`0/500/1500/3000 ms` checkpoints; eight zero-network fixture scenarios; two qualitative live
diagnostic runs; and 115 passing automated tests. Canonical collection behavior did not change.

## G2 — Competition investigator workflow — completed

Completed evidence: a localhost-only investigator workflow with a stage-by-stage case narrative,
direct provenance links, an accessible evidence-graph relationship table, neutral lead and
comparison language, separate noncanonical diagnostic cues, and a deterministic offline judge demo
builder. Optional comparison documents are displayed only after their case manifests, evidence, and
entity references re-verify. G2 changed no collector, diagnostic, extraction, graph, candidate,
comparison, bind, or deployment behavior.

## G3 — Demonstration and evaluation package — completed

Completed evidence: a hash-backed fixture-label manifest targeting `e55c161` / `gemastik-g2`; a
fail-closed, zero-network G3 verifier that creates a new sanitized demo and report outside immutable
case directories; evaluator guide and checklist; an implemented threat-model diagram; and a concise
presentation storyboard. G3 changes only the evaluator wrapper, documents, labels, and tests. Live
availability remains observational and never becomes benchmark truth.

## Explicitly out of scope until separately approved

- Deeper crawling or candidate-domain crawling.
- New external discovery sources.
- AI-derived relationship conclusions or scoring-weight changes.
- Login, form submission, CAPTCHA handling, or evasion.
- Public hosting, multi-user access, authentication, or remote APIs.
