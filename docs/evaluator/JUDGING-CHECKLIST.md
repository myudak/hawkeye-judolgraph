# Judging checklist

Target baseline: `gemastik-g2` / `e55c1610c4e5a0a31891e3a69944aa1ffe2648ac`.

Use this checklist against observable behavior, artifacts, and local commands—not marketing claims.

| Check | Where to verify | Pass condition |
| --- | --- | --- |
| □ Demo starts fully offline | `python -m hawkeye demo` and `hawkeye serve` | No VPN, login state, internet, live capture, or URLScan query is needed. |
| □ Only localhost is used | Console address and `hawkeye/review_app/server.py` | Browser opens `127.0.0.1`; server has no `--host` option. |
| □ No external requests occur | UI source/static tests and strict CSP | Console loads only `/assets` and `/api` on its own origin; no remote preview/embed/analytics route exists. |
| □ Artifacts pass integrity checks | `gemastik-g3-report.json` / **Evidence inventory** | All demo cases are `verified`; artifact hashes and paths re-verify before display. |
| □ Seed, capture, entities, graph, provenance are visible | `demo-harbor` console view | **Investigation path**, ledger, entities, graph table, and evidence IDs are present. |
| □ Graph has an accessible table | **Evidence graph — accessible relationship table** | Source, relationship, target, supporting evidence, and status are readable without a visual graph. |
| □ Lead stays non-conclusive | **Pending candidate leads** | The page says **Pending lead** and **Relationship: not determined**; no candidate navigation occurs. |
| □ Score is not an ownership probability | **Offline comparison results** | The page says **Evidence-similarity score** and **Review status: needs review**. |
| □ Diagnostic is noncanonical | **Render diagnostic** | UI says it cannot replace canonical HTML, screenshots, entities, graph, or scoring. |
| □ Restricted capture stays clean | `demo-restricted` | Artifact evidence remains available but no target-content entities or leads appear. |
| □ Human review remains required | Header and final workflow step | Console says human review is required and stores no conclusion. |
| □ Security headers and local restrictions remain | `tests/test_review_app.py` and verifier | CSP, COOP, CORP, referrer policy, no CORS, Trusted Host, and loopback bind tests pass. |
| □ Verification suite succeeds | `python tools/verification/verify_gemastik_demo.py --output <new-dir>` | Report contains `PASS` for baseline, labels, integrity, pytest, ruff, mypy, and `git diff --check`. |

Do not award evidence credit for claims such as “confirmed mirror,” “same owner,” “criminal network,”
or an ownership probability: those interpretations are deliberately prohibited by the benchmark
labels and the console language.
