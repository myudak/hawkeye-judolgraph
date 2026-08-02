# Gemastik local judge demo

This walkthrough is a deterministic, offline G2 fixture corpus. It uses the same case schemas,
verified loader, comparison validator, APIs, and localhost console as ordinary local cases. It is
not a mock web page and it never requires a VPN, internet access, browser login state, live
collection, or an external discovery query.

## Prepare a new demo directory

From the repository root, run:

```powershell
python -m hawkeye demo --output verification-output/gemastik-demo
python -m hawkeye serve `
  --cases verification-output/gemastik-demo/cases `
  --comparisons verification-output/gemastik-demo/comparisons `
  --port 8760
```

Then open `http://127.0.0.1:8760` locally. The `demo` command refuses to overwrite an existing
output directory. Delete or choose a different output directory deliberately before running it
again; do not use a real live capture as the demo fixture.

## Seven-minute walkthrough

1. Select `demo-harbor` from the verified case index. Point out that the console labels itself
   local, read-only, and human-review-only.
2. Read the **Investigation path** left to right: seed, bounded capture, deterministic observations,
   evidence graph, pending leads, offline comparisons, and human review. Each stage states its
   boundary as well as what exists.
3. Open **Capture ledger** and **Evidence inventory**. The evidence IDs are direct, verified local
   artifact references. The HTML artifact downloads as `text/plain`; the console never inserts its
   content into the UI.
4. Use **Observed entities** and the **Evidence graph — accessible relationship table** to trace a
   displayed observation or edge back to its evidence ID. Structural rows and observed-evidence rows
   are labeled separately.
5. Open the reason beneath **Pending candidate leads**. It says **Pending lead** and
   **Relationship: not determined**. The triage number is not an ownership, mirror, or legal claim.
6. Inspect the separate **Render diagnostic** and **Offline comparison results** panels. Diagnostics
   are explicitly noncanonical. The comparison uses **Evidence-similarity score** and
   **Review status: needs review**, never a probability or conclusion.
7. Select `demo-restricted` to demonstrate the limitation path: artifacts are preserved, but the
   UI says that canonical target content was not usable and shows no extracted target-content facts.

## Safety and accessibility checks to demonstrate

- Use keyboard Tab and the skip link; focus indicators are visible. The relationship table remains
  usable without a visual graph, and narrow screens retain horizontal table access.
- The console makes only same-origin requests to its own `/api` and `/assets` routes. It has no
  remote fonts, previews, analytics, write endpoints, or proxy behavior.
- `127.0.0.1` is the only bind address. Trusted-Host, CSP, COOP, CORP, referrer, cache, and
  content-type protections remain active on success and error responses.
- The three fixture case packages use reserved `.invalid` names and generic diagrams. They contain
  no copied branding, real operator data, live site content, or claim about any real domain.
