# Judge guide — HAWK-EYE / JudolGraph

## The problem

Public-web investigations are often reduced to screenshots, copied URLs, and asserted
relationships. That loses provenance: a reviewer cannot tell what was actually captured, what was
deterministically derived, and what still needs human judgment.

## What HAWK-EYE does

HAWK-EYE takes one public seed through a deliberately bounded, evidence-first workflow:

```text
Public seed → bounded capture → hashed local artifacts → deterministic observations
→ evidence graph → Pending lead → offline comparison → human review
```

The implementation preserves HTML and screenshot artifacts before extracting deterministic signals.
Each derived entity and graph edge points back to local evidence. Candidate output is explicitly a
**Pending lead** with **Relationship: not determined**. Offline comparison reports an
**Evidence-similarity score** with **Review status: needs review**.

## What it deliberately does not claim

The system does not claim ownership, mirror confirmation, criminality, legal status, or an
ownership probability. It does not log in, bypass a CAPTCHA, bypass geographic restrictions, submit
forms, follow generated candidate domains, or use AI to infer relationships. It is a single-machine,
read-only localhost tool, not a public service.

## Evidence and provenance model

The case loader accepts only completed packages whose JSON, artifact paths, hashes, images, evidence
references, graph references, and candidate references verify locally. `case.json`, `pages.json`,
`evidence.json`, `entities.json`, `graph.json`, and optional candidate artifacts form the core case
package. Captured HTML is served only as an inert `text/plain` attachment; it is never inserted into
the console DOM.

Optional comparison JSON is a separate companion. The console re-verifies its two source case
manifests, artifact paths/hashes, and entity references before showing a score. An invalid companion
becomes an integrity warning instead of a result.

## Safety boundaries

The collector limits public seed navigation to safe HTTP(S) destinations and a small same-site crawl.
The console itself is bound only to `127.0.0.1`; it permits only loopback Host headers, has no CORS,
no write API, no proxy route, no remote fonts/assets/previews, and strict CSP/COOP/CORP/referrer
headers. See [the implemented threat model](../security/THREAT-MODEL.md) for mitigations and residual DNS
TOCTOU risk.

## Start the fully offline demo

The G2 demo builder is the only evaluator demo input. It creates generic fixture cases using reserved
`.invalid` labels, local images, and real HAWK-EYE schemas; it does not collect a live site.

```powershell
python -m hawkeye demo --output verification-output/gemastik-demo
python -m hawkeye serve `
  --cases verification-output/gemastik-demo/cases `
  --comparisons verification-output/gemastik-demo/comparisons `
  --port 8760
```

Open `http://127.0.0.1:8760`. The UI uses existing read-only `/api/cases` and artifact routes; it
does not call a remote source. The comparison policy shown by the demo is
`v0.3-offline-comparison-1`.

## Primary walkthrough — 5 to 8 minutes

1. **0:00–0:45 — framing.** Select `demo-harbor`. Confirm the header says local, read-only, and
   human-review-required. Explain the investigation path from seed to human review.
2. **0:45–1:45 — bounded capture.** Open **Capture ledger** and read the recorded content outcome,
   page limit, depth limit, and HTML/screenshot evidence IDs. Emphasize that the console does not
   revisit the seed.
3. **1:45–3:00 — provenance.** In **Evidence inventory**, open a stored HTML reference and verify
   it downloads as text. Use **Observed entities** and the accessible relationship table to trace an
   observation or graph edge back to `evidence-page-001`.
4. **3:00–4:00 — uncertainty.** Open **Pending candidate leads**. The UI says **Pending lead** and
   **Relationship: not determined**. Its triage value is not a conclusion and does not trigger a
   crawl.
5. **4:00–5:15 — comparison.** Inspect **Offline comparison results**. It shows separate component
   statuses and an **Evidence-similarity score**. The adjacent **Review status: needs review** is
   deliberately not an ownership probability.
6. **5:15–6:00 — diagnostics.** Point out the separate render diagnostic. It references canonical
   evidence but cannot replace the saved HTML, screenshot, entities, graph, or score.
7. **6:00–7:00 — limitation case.** Select `demo-restricted`. It preserves artifacts but labels
   target content as not usable and shows no extracted target-content entities.
8. **optional depth — verification.** Run the verifier below and inspect its hash-backed report.

## Verify outputs

Use a new directory every time:

```powershell
python tools/verification/verify_gemastik_demo.py --output verification-output/gemastik-g3
```

Successful output has `PASS` results for the frozen `gemastik-g2` target, sanitized-demo manifest,
benchmark labels, case/reference integrity, documentation checks, pytest, ruff, mypy, and `git diff
--check`. The report may use `NOT APPLICABLE` only for a deliberately skipped local diagnostic mode;
the judge command above does not skip quality gates. `OBSERVATIONAL ONLY` is reserved for live notes,
which are not benchmark truth.

## Known limitations

- Live pages can vary by time, location, session, VPN, and restriction state. They are not test
  truth.
- G1 observed some separate live render changes within a fixed three-second window. This does not
  identify a cause, prove a later page is canonical, or change collection behavior.
- Chromium resolves hostnames independently after application validation. This residual DNS TOCTOU
  risk is mitigated and documented, not claimed eliminated.
- Candidate leads and comparison results require human review. HAWK-EYE does not record that human
  conclusion or make it durable.
