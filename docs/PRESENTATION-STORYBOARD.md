# Gemastik presentation storyboard

Target baseline: `gemastik-g2` / `e55c1610c4e5a0a31891e3a69944aa1ffe2648ac`.

This is a scene plan, not a new presentation application. Use the sanitized local demo and existing
artifacts only. Do not invent accuracy, adoption, performance, legal-impact, ownership, or
criminality statistics.

| Scene | Single message | Exact screen or artifact | Supporting evidence | Do not claim | Time |
| --- | --- | --- | --- | --- | --- |
| 1. Problem | Public evidence is hard to audit when screenshots and assertions lose provenance. | `docs/evaluator/JUDGE-GUIDE.md` problem statement. | Documented evidence/provenance model. | That every public page is malicious or related. | 0:30 |
| 2. One seed | The workflow starts from one public seed, not a domain graph guessed in advance. | **Investigation path** on `demo-harbor`. | Seed stage and capture ledger. | That the demo represents a real live site. | 0:25 |
| 3. Safe bounded collection | Collection is deliberately limited before evidence derivation begins. | Capture ledger; `CrawlConfiguration` fields. | Depth/page/redirect limits and safe URL policy. | Complete Internet coverage or bypass capability. | 0:35 |
| 4. Preserve first | Raw HTML and screenshot artifacts are hashed local evidence. | **Evidence inventory** and one inert HTML attachment. | Evidence ID, SHA-256, content disposition. | That captured HTML executes in the console. | 0:35 |
| 5. Deterministic observations | Entities are derived from saved evidence, not an opaque AI claim. | **Observed entities**. | Evidence ID, page ID, extraction confidence. | That an entity proves ownership or intent. | 0:35 |
| 6. Explainable graph | A graph relationship can be read without trusting a visualization. | **Evidence graph — accessible relationship table**. | Source, relationship, target, evidence, status columns. | That structural edges prove an external relationship. | 0:35 |
| 7. Pending candidate | Candidate discovery is a review queue, not a conclusion or crawl instruction. | **Pending candidate leads** reason disclosure. | Supporting evidence/observation IDs. | “confirmed mirror,” “same owner,” or automatic candidate navigation. | 0:35 |
| 8. Offline comparison | Similarity is decomposed into evidence-backed components. | **Offline comparison results**. | `v0.3-offline-comparison-1`, component rows, provenance. | An **Evidence-similarity score** is an ownership probability. | 0:40 |
| 9. Uncertainty and review | Diagnostics and scores stay separate from canonical evidence and human judgment. | Render diagnostic + workflow step 7. | **Review status: needs review**; noncanonical diagnostic copy. | That a later render checkpoint is the true page. | 0:35 |
| 10. Security and auditability | The system constrains both collection and local review surfaces. | `docs/THREAT-MODEL.md`. | Loopback bind, CSP, hash verification, residual DNS TOCTOU note. | Risk elimination or public deployment readiness. | 0:35 |
| 11. Offline judge demo | Evaluation can be repeated with sanitized artifacts and no network dependency. | `python -m hawkeye demo`, then `hawkeye serve`. | `docs/DEMO.md`; fixture cases use `.invalid`. | That the demo is live evidence. | 0:35 |
| 12. Verification and why it matters | Judges can reproduce the evidence story and see its limits. | `python scripts/verify_gemastik_demo.py --output <new-dir>`. | Hash-backed G3 report, test suite, checklist. | That HAWK-EYE replaces investigator judgment. | 0:40 |

Total primary presentation time: approximately 7 minutes. Reserve 1–3 optional minutes to navigate
the `demo-restricted` limitation case, inspect an HTML attachment, and open the generated G3 report.
