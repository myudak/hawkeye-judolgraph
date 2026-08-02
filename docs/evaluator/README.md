# HAWK-EYE evaluator package

This is the competition-facing wrapper for the frozen **Gemastik G2** baseline:

- Commit: `e55c1610c4e5a0a31891e3a69944aa1ffe2648ac`
- Tag: `gemastik-g2`
- Evaluation-package version: `gemastik-g3-1`

It helps a judge inspect and verify the implemented G0–G2 system without reading the development
history. It does not introduce a new collector, API, UI surface, deployment model, or inference
method.

Start here:

1. [Judge guide](JUDGE-GUIDE.md) — the 5–8 minute primary walkthrough.
2. [Judging checklist](JUDGING-CHECKLIST.md) — observable claims and where to verify each one.
3. [Threat model](../THREAT-MODEL.md) — implemented boundaries, mitigations, and residual risks.
4. [Presentation storyboard](../PRESENTATION-STORYBOARD.md) — a concise, evidence-led narrative.

Run the package verifier from the repository root using a **new** output directory:

```powershell
python scripts/verify_gemastik_demo.py --output verification-output/gemastik-g3
```

The verifier creates the sanitized demo through the frozen G2 builder, checks its manifest and
benchmark-label hashes, validates all local references, runs the automated quality suite, and writes
`gemastik-g3-report.json` plus `SUMMARY.md` under the requested output directory. It refuses to
overwrite a directory and exits nonzero when a required check fails. When the output is inside this
repository, it must be under ignored `verification-output/` or `evaluation/reports/`; the verifier
rejects output inside the frozen runtime or other checked-in package inputs.

The generated report records both the sanitized-demo manifest hash and the benchmark-label manifest
hash. It also checks that `gemastik-g2` still resolves to the frozen commit and that the `hawkeye/`
runtime tree has not drifted from it. G3 documentation and script files are intentionally outside
that frozen runtime tree.
