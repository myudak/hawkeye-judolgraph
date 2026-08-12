# Evaluation Protocol

## Purpose

Evaluation measures engine behavior and evidence integrity. It does not evaluate criminality,
ownership, or calibrated mirror-detection accuracy.

## Windows distribution acceptance

A release candidate is accepted only when a clean native Windows build proves all of the following:

1. locked Python and JavaScript dependencies install without credentials;
2. the generated React bundle and controlled fixture are present in the frozen application;
3. the packaged executable passes its `spawn` worker probe and launches bundled Chromium without a
   first-run download;
4. the packaged server becomes healthy on an ephemeral loopback port and serves the actual React
   shell;
5. the executable closes with its child process tree and leaves user data outside the installation;
6. portable ZIP, optional installer, and SHA-256 manifest contain no `.env`, LLM credential, live
   capture, or workspace database.

GitHub Actions repeats this gate on a native Windows runner before artifact upload or tagged release.
Tesseract availability is reported separately because OCR is optional outside the Docker image.

## Corpus layout

```text
evaluation/
  fixtures/   deterministic synthetic policy fixtures
  manifests/  checked-in public URL definitions and collection limits
  expected/   bounded invariant sets for deterministic scenarios
  reports/    generated local reports (gitignored)
  live-cases/ generated local live case packages (gitignored)
```

## Two layers of evidence

1. **Deterministic fixtures** are synthetic or minimized local reproductions. They are the source
   of automated-test truth.
2. **Live manifests** describe opt-in public evaluations. They record only invariant expectations;
   content, exact entities, screenshots, redirects, or scores are observations, not stable truth.

## Manifest contract

Each JSON manifest contains:

- `evaluation_id`, `schema_version`, input URL, purpose, and source type;
- non-interactive bounded collection policy;
- a reference and SHA-256 for the deterministic policy-fixture manifest;
- invariant expectations such as preservation, crawl budgets, external-document behavior, and
  `needs_review` semantics;
- environmental restrictions and a statement that live results are opt-in only.

## Read-only report command

After a completed local case exists, run:

```powershell
python -m hawkeye evaluate <manifest.json> <completed-case-directory> --report <new-report.json>
```

The command reads and integrity-verifies the case before evaluating it. It performs no network
request and refuses to overwrite an existing report.

## Render-diagnostics protocol (G1)

Render diagnostics are a distinct opt-in operation, not a modification of collection:

```powershell
python -m hawkeye diagnose <completed-case-directory> --mode live
```

For deterministic local fixtures, `--mode fixture --allow-loopback-for-testing` also requires
`HAWKEYE_TEST_MODE=1`. The operation re-verifies the completed case and page, then writes one new
`diagnostics/render-diagnostics.json` file. It is rejected if that file already exists.

The fixed schedule is `0`, `500`, `1500`, and `3000` milliseconds after navigation/load
completion. The additional wait budget is exactly three seconds and never adapts. Each checkpoint
records document ready state, HTML bytes, visible-text character count, element/anchor/image/
iframe/canvas counts, document height, screenshot hash/bytes/entropy, and adjacent deltas. Neutral
labels are `stable_across_checkpoints`, `changed_after_initial_capture`,
`continued_changing_at_budget_end`, `low_information_across_checkpoints`, and `diagnostic_error`.

The diagnostics do not alter canonical HTML/screenshots, `content_usable`, entities, graph edges,
candidates, comparison scores, or review semantics. They do not interact with pages, impersonate
a user agent, install stealth behavior, bypass restrictions, or fetch candidate domains. A change
observed within the fixed schedule is not proof of its cause or of which checkpoint is the true
canonical page.

The deterministic G1 scenarios live under `tests/fixtures/` and cover: immediate static content;
rendering after 500 ms; rendering after 1,500 ms; continued change at the budget end; permanent
sparse output; canvas-heavy output; DOM growth with unchanged pixels; and pixel change with stable
DOM. Their tests use relational assertions rather than exact screenshot byte sizes or live-site
values.

## Investigator workflow and demo protocol (G2)

The local console displays only cases accepted by `CaseLoader`. G2 presentation does not cause a
browser collection, DNS lookup, external fetch, candidate crawl, comparison run, or persistent
human decision. It renders captured values as bounded text and serves saved HTML as an inert
attachment. Optional comparison documents are displayed only when their case manifests, evidence
references, and entity references verify against the configured local cases root; invalid documents
surface an integrity warning.

The reproducible judge walkthrough is documented in `docs/DEMO.md`. Build it with `python -m
hawkeye demo --output <new-directory>`, then serve its `cases/` and `comparisons/` subdirectories
through the existing loopback-only console. The fixture uses reserved `.invalid` labels and generic
static images. It is a local demonstration input, not live availability or competition truth.

## Frozen evaluator package protocol (G3)

G3 evaluates the frozen `gemastik-g2` runtime at
`e55c1610c4e5a0a31891e3a69944aa1ffe2648ac`. Its label source is
`evaluation/benchmarks/gemastik-g2-labels.json`, which records fixture-only expected properties and
prohibited interpretations. It covers normal usable content, restricted capture, a pending lead,
offline comparison with `needs_review`, a fixture low-information component, a noncanonical render
diagnostic, and an invalid provenance-companion warning. Live observations are excluded from labels.

Run the fail-closed offline verifier with a new output directory:

```powershell
python scripts/verify_gemastik_demo.py --output verification-output/gemastik-g3
```

The command verifies the frozen tag and runtime tree, blocks normal DNS/socket connection primitives
while building/reading the sanitized G2 demo, checks the demo-manifest and label-manifest hashes,
uses the existing verified loader for integrity/reference validation, checks evaluator documentation,
runs pytest/ruff/mypy/`git diff --check`, and writes `gemastik-g3-report.json` plus `SUMMARY.md`
outside case directories. It refuses existing output and returns nonzero on a required failure.
Report statuses are `PASS`, `FAIL`, `NOT APPLICABLE`, and `OBSERVATIONAL ONLY`.

## Live collection protocol

- Use a fresh, unauthenticated browser context where practical.
- Do not log in, solve CAPTCHAs, submit forms, click gambling/payment/registration/messaging
  actions, download files, or reuse cookies to help the collector.
- Persist live output only under ignored `evaluation/live-cases/` or `verification-output/`.
- Generate an evaluation report from the completed local case; the report records manifest and
  artifact hashes, engine/commit metadata, observed outcome, invariant results, and environmental
  restrictions.

## Chrome observation protocol

Chrome is qualitative comparison evidence only. Record the input URL, timestamp/timezone, final
visible URL, broad VPN state/exit country without provider details, whether an existing session was
present, visible redirect/challenge/consent/restriction behavior, concise notes or a screenshot,
and the collector case being compared. Do not treat the observation as a relationship conclusion or
as test truth.

## Rendered-content gap and post-G4A observations

The initial G0 live observations showed rich visible landing content in Chrome while the isolated
collector preserved substantially sparser title-led DOMs and dark screenshots. The local
`delayed-script-render-shell-v1` fixture reproduced the narrow timing symptom without copying live
content. Canonical capture now uses mandatory base checkpoints plus bounded 5/8-second settle
extensions, records browser-visible text, and may extract explicitly provisional evidence from a
readable page that remains dynamic instead of silently discarding it.

On 2026-08-03 the owner-authorized post-G4A matrix ran exactly once against each of the 12 supplied
targets. Eleven produced verified navigation captures; `888sport.com` stopped at the request
budget. All content-looking captures remained limited and therefore produced no automatic semantic
extraction. Betfair and Paddy Power were recorded as geographic restriction observations, Sky
targets as unavailable, and bet365 as an access challenge. The two QQ observations were preserved
with screenshot/readiness evidence and limited status. These artifacts remain ignored under
`evaluation/live-cases/gemastik-2026-08-03-g4a-fixed/`; they are local qualitative robustness
evidence, not benchmark truth and not redistribution material.

A final corrective QQ validation on the same date used the unified product path. It captured the
seed and `/MobileExplore`, recorded 11 provisional seed/crawl observations, used a strict
`gpt-5.6-terra` decision to select the server-issued Contact reference, and saved the Indonesian
`/Contact` screenshot/HTML/text/JSON. The interaction artifact yielded one telephone, one WhatsApp,
and one Telegram observation while `qq101uok.com` remained waiting for explicit approval. This
remains ignored qualitative evidence, not benchmark truth.

## Metrics for future labeled fixtures

- Artifact-integrity pass rate.
- Capture-outcome classification correctness.
- Entity-extraction precision and recall.
- Candidate-generation precision on labeled fixtures.
- Comparison-component reproducibility.
- Evidence-reference resolution rate.
- Crawl-budget compliance.
- Unsafe-request blocking rate.

Two live examples are not a benchmark; no accuracy or calibration claim may be made from them.

## G4–G8 controlled interaction benchmark

`evaluation/fixtures/controlled-interactions-v1.json` contains exactly ten authoritative scenarios:
visible evidence, modal, menu, tab, iframe, redirect/new tab, ambiguous action, login/register,
download, and no useful hidden evidence. Each records expected observable, required interaction,
candidate/relation when applicable, and prohibited controls.

Run all scenarios in static, rule-based, and agent-assisted deterministic-fallback modes with:

```powershell
python -m hawkeye benchmark `
  --output <new-directory> `
  --agent-attempts 3
```

The command writes `raw-results.json` and `BENCHMARK_RESULTS.md`, refuses an existing directory, and
reports approach comparison, per-scenario results, policy safety, provenance completeness, agent
nondeterminism, and failure breakdown. The checked-in result is under
`evaluation/benchmarks/g4-g9-controlled-results/`.

Scenario `safe-menu` is deliberately stateful: action one reveals a second safe Contact control,
and action two reveals the observable. The single-pass rule baseline therefore records 0.8571
observable recall and 0.9000 task success; the delta-aware agent-assisted fallback records 1.0000
for both with mean 0.7000 actions. This difference demonstrates feedback-loop utility only inside
the ten synthetic scenarios.

Metrics are observable recall/precision, task success, provenance completeness, unsafe-action
block rate, mean actions/runtime, candidate relation support, and replay consistency. Timing is
measured locally and rounded to milliseconds. Synthetic results must never be described as live
accuracy, ownership probability, operator identification, criminality, or legal status.

The post-G9 indicator checks are observation-level and deterministic. Fixtures assert direct-term
counting, same-page context for typed transaction/offer evidence, and non-counting of generic
contacts/payments/links. Acceptance requires every counted classification to resolve its page,
source artifact, and screenshot reference. The output is an integer evidence count; percentage,
probability, and site-level legality labels are prohibited.

The progressive-scan test uses only the loopback fixture server. It must observe real capture,
artifact-preservation, extraction, indicator, graph, and completed stages through the job API. A
separate forced short wall-clock test must terminate the spawned browser worker without leaving the
test process waiting indefinitely. Live URLs remain qualitative and are not used for these tests.

External candidate mode stops at an approval event. A user may explicitly approve one directly
observed candidate, after which the product performs one page/depth-zero collection and proposes
only a `publicly_links_to` assertion for review. The official benchmark and demo still use reserved
fixture data and no external network.

## Monorepo and container acceptance

Current source checks run from the repository root through `pnpm check`. Python imports resolve
from `apps/api/src`; frontend checks resolve from `apps/web`; controlled fixtures and pytest node
IDs remain under their historical root paths. `pnpm package` must produce a wheel containing the
complete generated UI and the ten-scenario manifest.

Container acceptance uses the same loopback fixtures, never live judol URLs. It must confirm a
non-root process, `/health`, Tesseract availability, browser capture, child cleanup after a forced
wall timeout, loopback-only host publishing, and persistence across `docker compose down` / `up`.
If the Docker daemon or pinned browser download is unavailable, that gate is reported as blocked;
successful Compose syntax or a cached unit test is not presented as a successful container run.
