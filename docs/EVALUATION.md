# Evaluation Protocol

## Purpose

Evaluation measures engine behavior and evidence integrity. It does not evaluate criminality,
ownership, or calibrated mirror-detection accuracy.

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

## Known rendered-content completeness gap

The initial G0 live observations showed rich visible landing content in Chrome while the isolated
collector preserved substantially sparser title-led DOMs and dark screenshots. This does not
classify either site as blocked, challenged, inaccessible, related, or unsafe; it identifies a
possible headless, user-agent, timing, or site-behavior difference. The fully local
`delayed-script-render-shell-v1` fixture captures the narrow symptom without copying any live
content. G0 intentionally changes no collector behavior. G1 must define bounded completeness
indicators and timing budgets before considering a capture-readiness change.

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
