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

## G1 — Rendered-content completeness diagnostics and bounded capture-readiness evaluation — proposed, not approved

Potential work: define reproducible completeness indicators and bounded render-readiness timing
budgets for sparse initial shells that later render client-side. It must not introduce CAPTCHA
bypass, stealth plugins, unrestricted delays, arbitrary user-agent impersonation, or interaction
with login controls.

## G2 — Competition investigator workflow — proposed, not approved

Potential work: polish the V1 investigator narrative, improve evidence-graph explanation,
comparison presentation, accessibility, and demo flow using only verified local artifacts. This
does not authorize public deployment, new crawling behavior, or changes to scoring semantics.

## G3 — Demonstration and evaluation package — proposed, not approved

Potential work: stable sanitized demo dataset, evaluator guide, benchmark labels for deterministic
fixtures, threat-model diagram, and a concise Gemastik presentation narrative. Live availability
must never become a test dependency.

## Explicitly out of scope until separately approved

- Deeper crawling or candidate-domain crawling.
- New external discovery sources.
- AI-derived relationship conclusions or scoring-weight changes.
- Login, form submission, CAPTCHA handling, or evasion.
- Public hosting, multi-user access, authentication, or remote APIs.
