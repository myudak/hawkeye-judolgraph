# JudolGraph / HAWK-EYE Goal

## Product problem

Public web investigations often need a reproducible way to preserve what a domain showed at a
specific time, map extracted public evidence, and distinguish an unverified lead from a supported
fact. Ad hoc screenshots, manual browsing, and asserted relationships are not enough for a
competition demonstration or an investigator workflow.

## Gemastik objective

Develop JudolGraph / HAWK-EYE into a competition-ready, evidence-driven investigator workspace.
It must demonstrate a clear workflow from a public seed URL to bounded evidence capture,
deterministic extraction, an auditable graph, relationship-neutral leads, and explainable offline
comparison. The result must be reproducible locally and explicit about uncertainty.

## Intended user

A researcher, investigator, evaluator, or competition judge who needs to inspect public web
evidence without relying on opaque AI conclusions or automatically following every discovered
domain.

## Product principles

- Preserve public evidence and its provenance before deriving conclusions.
- Keep collection, extraction, candidate generation, and comparison deterministic by default.
- State uncertainty clearly: candidates are `pending`; comparison results are `needs_review`.
- Make every displayed fact traceable to an artifact, a verified manifest, or a documented
  deterministic rule.
- Prefer secure local defaults over a broader but unsafe deployment surface.

## Non-goals

- Determining ownership, criminality, or legal status of a domain.
- Bypassing access controls, CAPTCHAs, geographic restrictions, rate limits, or authentication.
- Automatically crawling candidate domains, logging in, submitting forms, downloading files, or
  transacting with any site.
- Publishing the V1 console, collecting private data, or representing similarity as probability.

## Completion standard

A competition-ready milestone needs a understandable investigator story, a stable local demo,
fixture-based automated tests, evidence traceability, a documented threat model and limitations,
safe defaults, explainable scores, and a reproducible evaluation protocol. A running command alone
does not meet this standard.
