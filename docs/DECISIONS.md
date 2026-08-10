# Architecture and Scope Decisions

## ADR-001 — Deterministic evidence pipeline

**Status:** accepted

Collection, extraction, candidate generation, and comparison use explicit deterministic rules and
persist provenance. AI may assist a future workflow only inside a separately documented,
evidence-backed boundary.

## ADR-002 — Leads are not conclusions

**Status:** accepted

Candidates remain `pending` with `relationship: null`; comparison emits an evidence-similarity
score with `needs_review`. Neither output may be labelled ownership, mirror confirmation, or
criminal attribution.

## ADR-003 — Bounded public collection

**Status:** accepted

Collection permits public HTTP(S) seeds only, applies URL and DNS safety checks, and remains bounded
to same-site depth `0..1` and five HTML pages. It does not log in, submit forms, accept downloads,
or bypass restrictions. Candidate domains are never crawled automatically.

## ADR-004 — Local-only V1 console

**Status:** accepted

The review console binds only to `127.0.0.1`, permits only `127.0.0.1` and `localhost` Host
headers, ignores forwarded-host headers, has no CORS or write endpoints, and re-verifies artifacts
before delivery. Public deployment requires a new threat model, authentication, authorization, and
review milestone.

## ADR-005 — Reviewer conversation is advisory

**Status:** accepted

The designated Chrome conversation is a lead-agent-only architecture and security checkpoint.
Repository artifacts and executed verification take precedence. The conversation is neither shared
memory nor an execution worker, and it receives no secrets or large raw artifacts.

## ADR-006 — Live evaluation is opt-in and non-interactive

**Status:** accepted

Live public URLs are recorded as manifests and may be observed or collected only through bounded
non-interactive workflows. They are not unit-test truth. Raw captures remain ignored local data
unless redistribution is separately justified; deterministic fixtures are the test source of truth.

## ADR-007 — Residual DNS TOCTOU is documented

**Status:** accepted

The collector revalidates request destinations, but Chromium ultimately resolves hostnames itself.
Complete DNS-rebinding elimination would require network-layer IP pinning or a validating proxy.
This residual limitation is documented rather than hidden.

## ADR-008 — Rendered-content completeness is a separate capture concern

**Status:** accepted

Chrome observations of two opt-in live evaluations showed more visible landing-page content than
the isolated collector artifacts, which preserved title-led sparse shells and dark screenshots.
This is recorded as a rendered-content completeness gap, not as a challenge, failure, mirror, or
site conclusion. G0 adds a fully local delayed-render shell fixture but does not change collection,
classification, waiting, user-agent, screenshot, or scoring behavior; any fix belongs to G1.

## ADR-009 — G1 diagnostics are isolated and fixed-time

**Status:** accepted

G1 may create an opt-in `diagnostics/render-diagnostics.json` under an already-verified local
case. It re-navigates only the saved same-site page in a fresh non-interactive context and records
neutral measurements at `0`, `500`, `1500`, and `3000` milliseconds. The three-second wait budget
is fixed and does not adapt to a page. Diagnostics reference canonical evidence but do not modify
or replace canonical HTML, screenshots, classification, entities, graph edges, candidates, or
comparison scores. They do not determine why a page changed.

## ADR-010 — G2 presents verified artifacts without creating review facts

**Status:** accepted

G2 may improve the localhost investigator console only by projecting already verified local case
data. Every shown entity, graph edge, candidate reason, and comparison component carries a visible
case/evidence/observation reference when it is locally available. Captured HTML remains an inert
`text/plain` attachment and all hostile artifact values are bounded text, never inserted as HTML or
converted to remote links.

Optional comparison documents live in a separately configured local directory. Before display, the
console verifies both referenced case manifests, each evidence path/hash, and entity references;
an invalid document becomes an integrity warning rather than a displayed score. Optional G1
diagnostics are separately validated against the current case manifest and remain explicitly
noncanonical. The UI has no write route, review-decision store, remote asset, external fetch,
collection trigger, scoring change, or public bind.

## ADR-011 — G3 verifies a frozen runtime through an external evaluator wrapper

**Status:** accepted

G3 targets the `gemastik-g2` tag at `e55c1610c4e5a0a31891e3a69944aa1ffe2648ac`. Its verifier is a
checked-in script, not an engine or API change. Before producing a report, it checks that the tag
still resolves to the target and that the `hawkeye/` runtime tree has not drifted from G2. G3
documentation, labels, scripts, and tests are intentionally outside that frozen runtime boundary.

The verifier creates a new sanitized demo directory under caller-selected ignored output, blocks
normal DNS/socket connection primitives while it builds and reads fixture inputs, validates case and
comparison references through the existing loader, checks hash-backed labels, and writes a report
outside immutable case directories. It refuses an existing output directory and returns nonzero for
required failures. Its report distinguishes `PASS`, `FAIL`, `NOT APPLICABLE`, and
`OBSERVATIONAL ONLY`; no live result becomes permanent benchmark truth.

## ADR-012 — Canonical capture uses fixed readiness checkpoints

**Status:** accepted

G4A promotes the fixed 0/500/1500/3000 ms measurement schedule into canonical collection. The
final checkpoint is canonical, browser `innerText` is visible-text truth, and capture adequacy is
kept independent from navigation and access outcome. Five megabytes is the persistence limit while
two megabytes is the automatic extraction limit. Oversize documents preserve bounded partial
evidence and never become navigation errors.

## ADR-013 — Semantic observations precede assertions

**Status:** accepted

G4B adds immutable semantic observations with artifact and screenshot provenance. Observations do
not themselves assert ownership or relationship. Automatic semantic extraction is fail-closed for
limited captures; visible branding is a `ClaimedBrandIdentity`, not verified ownership.

## ADR-014 — Interactions use stable references and server policy

**Status:** accepted

G5 exposes six narrow tools over snapshot-bound element references. Every action passes server-side
keyword, form, download, destination, and budget checks. The ten controlled scenarios are the
authoritative interaction corpus; real chat widgets remain blocked by default.

## ADR-015 — Codex is optional and capability-gated

**Status:** accepted

G6 enables a model path only when the fixed loopback probe advertises the structured capabilities
needed for the tool loop. Unknown support is not guessed. Invalid schemas receive two bounded
attempts before the deterministic fallback emits the same normalized decision shape.

## ADR-016 — Recollection and review are append-only boundaries

**Status:** accepted

G7 allows Page B recollection only for reserved synthetic fixtures. Automatic fixture mode may
recollect immediately; approval-gated controlled mode must persist `candidate_page.approved` before
the deterministic fixture recollection helper can store Page B. No external candidate network
collection is enabled. Assertions reference both page observations and artifacts; SQLite review
history is append-only and current status is derived.

## ADR-017 — Stored events build progressive graph truth

**Status:** accepted

G8 persists investigation events before reduction. Graph state is idempotently rebuilt from the
event log and is independent of the optional animation queue. Search leads, collected evidence,
candidate assertions, verified relations, and rejected relations remain visually distinct.

## ADR-018 — Canvas animation is a disposable evidence projection

**Status:** accepted

The preliminary console uses a dependency-free 2D canvas inspired by the interaction vocabulary of
the owner-supplied WebGraph reference: continuous drawing, force relaxation, glow, edge particles,
drag, pan, zoom, hit-testing, search, focus, and replay. HAWK-EYE does not copy WebGraph's generated
site inventory or synthetic performance/risk values. Canvas state is rebuilt from verified case
packages or the event reducer, and the DOM inspector/timeline remains the accessible evidence path.

The local default may prefer an ignored, owner-authorized QQ observation when that case root is
explicitly supplied to `hawkeye serve`. The application does not bundle, commit, or redistribute
that live screenshot; deterministic `.invalid` fixtures remain official demo and benchmark truth.

## ADR-019 — Useful bounded expansion replaces the one-page product path

**Status:** accepted; supersedes the fixed canonical-budget part of ADR-012 and the external
recollection restriction in ADR-016 for the preliminary MVP.

Every URL scan now performs one coherent workflow: up to three same-site pages at depth one,
mandatory readiness checkpoints with bounded settle extensions, verified or provisional semantic
evidence, a policy-permitted bounded agent objective, append-only events, and the progressive graph. A
readable page that remains dynamic may produce explicitly provisional evidence instead of being
discarded. No authentication, challenge, geo, rate-limit, or access-control bypass is added.

## ADR-020 — Direct links drive cross-case graph identity

**Status:** accepted.

Normalized hostnames merge direct public anchors with already verified local cases. Thus an observed
`888.com` anchor to an already captured `888casino.com` becomes a collected destination node; it
does not become an ownership claim. An unseen brand-related hostname remains a dashed candidate and
requires explicit collection approval. Generated candidates are never crawled automatically.

## ADR-021 — Strict Responses output is the Codex capability gate

**Status:** accepted; clarifies ADR-015.

The service discovers a model through the fixed loopback model route and must complete a strict
JSON-schema probe. The decision schema is normalized to strict required nullable fields. A selected
tool reference must exactly equal a server-issued safe reference. Codex never receives or executes
Playwright; transport or validation failure activates the deterministic fallback.

## ADR-022 — Contact routes reveal evidence; communication actions remain blocked

**Status:** accepted; clarifies ADR-014 and ADR-019.

A discovered same-site Contact, Hubungi Kami, or support-information control is a safe read-only
reveal target when it passes the stable-reference and server-policy checks. The runtime prefers it
for a contact-evidence gap, captures the resulting screenshot, HTML, visible text, and state JSON,
and emits phone, WhatsApp, Telegram, or email observations only when they are present in that
artifact. For locale-sensitive sites the interaction browser declares the Indonesian locale; an
equivalent `Contact Us` → `Hubungi Kami` label change does not invalidate an otherwise stable
reference. If a no-`href` SPA control does not navigate, one conventional same-origin Contact/Help
route may be opened after the click and the fallback URL is recorded in the audit artifact.

This does not authorize communication. Live Chat, form submission, message send, external-app
launch, login, registration, payment, download, CAPTCHA, and access-control bypass remain blocked.
Contact values are evidence-backed public observations, not operator identity or ownership claims.

## ADR-023 — Agent assistance is a bounded feedback loop, not one model click

**Status:** accepted; supersedes the one-action limit in ADR-019.

The objective loop admits three task IDs and at most five decisions/three interactions. Every
decision sees attempted references and the latest before/after observation delta. Repeated stale or
no-op outcomes stop explicitly. The authoritative `safe-menu` fixture requires a menu reveal and a
second Contact action; rule mode stops after the reveal, while agent-assisted fallback uses the
delta for step two. This is the measured source of the benchmark difference, not an intelligence or
live-web accuracy claim.

## ADR-024 — Exact cross-case joins and temporal diffs remain reviewable evidence

**Status:** accepted; clarifies ADR-020.

Only exact normalized identifiers from verified local case packages automatically produce a
cross-case pending assertion. Phone/WhatsApp/Telegram/email, redirect, download, and referral
matches retain both cases' artifact and observation references. Fuzzy similarity never becomes an
ownership probability. A new same-host capture is compared to the previous verified local snapshot
as added/removed/unchanged observable sets; it does not silently overwrite history.

## ADR-025 — Scroll, encapsulated DOM, and OCR are bounded capture extensions

**Status:** accepted.

Long pages receive one fixed middle/bottom/top read-only scroll sweep before the canonical final
state. Public links visible in open shadow roots and readable same-origin iframes may enter the same
depth/page-limited frontier; cross-origin frame isolation is not bypassed. Optional local Tesseract
OCR has byte, pixel, dimension, output, and timeout limits. Its status is always persisted, and any
derived signal is provisional with a human visual-confirmation limitation. Missing Tesseract is an
honest `unavailable` result.

## ADR-026 — The console is a three-view evidence instrument

**Status:** accepted; extends ADR-018.

The UI separates case creation, graph investigation, and report/export instead of placing every
control around the canvas. Canvas animation remains a projection of event truth. Capture-only mode
skips model-guided interaction and persists that stop reason. Markdown, JSON, and ZIP exports are
generated from the same verified run/event/review state and never upgrade a candidate into a
conclusion.

## ADR-027 — Judol indication is an evidence count, not a score

**Status:** accepted.

The preliminary product classifies verified semantic observations with a versioned deterministic
term policy. Direct controlled gambling language may count one observation; typed offer, payment,
referral, or tracking evidence counts only when the same captured page also has direct gambling
language. Public contacts and outgoing destinations remain OSINT evidence but never count merely
because they are co-located. Each counted item retains the observation, page, source artifact, and
screenshot reference.

The UI displays an integer count and category breakdown only. It does not display a judol
percentage, probability, risk score, legal finding, criminality claim, operator identity, or
ownership attribution. `0` means no controlled term matched the available classified evidence; it
does not claim the site is free of gambling content. The projection is computed when a verified case
is loaded, preserving existing immutable packages and append-only review data.

## ADR-028 — Live UI scans run as recoverable isolated jobs

**Status:** accepted.

A localhost-triggered live scan starts one in-memory job and delegates Playwright collection to a
spawned process. Collector callbacks expose bounded stage/detail snapshots; the UI polls those
snapshots and can resume the one active job after reload. The browser process has a 115-second hard
wall-clock boundary beneath the collector's existing page/case budgets. On timeout its process tree
is terminated and any initialized case record is changed from `running` to an explicit failed,
timed-out state. It is never returned through the verified completed-case loader.

Progress has no fabricated percentage. The displayed stages correspond to validation, browser
launch, case initialization, page capture, artifact preservation, optional OCR, extraction,
candidate generation, manifest verification, policy-gated agent work, indicator classification,
and graph reduction. A single-active-job rule prevents overlapping local browser captures from
competing for the same workspace.

## ADR-029 — React is a replaceable projection over existing evidence truth

**Status:** accepted; clarifies ADR-026.

The localhost console uses a React/TypeScript/Vite presentation layer built from the checked-in
shadcn/ui preset. This does not change any FastAPI contract, SQLite table, case package, event
schema, graph reducer, review history, or network policy. Routes are lazy-loaded hash routes so the
FastAPI server needs no browser-route fallback and the initial page does not download the graph
workspace.

The presentation resolver maps persisted node/observation categories into Page, Contact, Brand,
Transaction, Offer, Destination, Candidate, or Other visual kinds with a deterministic fallback.
Filters, layout, animation, minimap, search, selection, and replay cannot create or upgrade
evidence. Artifacts and screenshots stay in the provenance inspector; they are not graph nodes.
No UI state may imply ownership, identity, criminality, legality, or a verified relationship unless
the persisted evidence/review state explicitly supports that wording.

## ADR-030 — Graph V2 is an evidence-centered semantic orbit, not a topology claim

**Status:** accepted; extends ADR-029.

The graph presentation centers the investigated site and distributes evidence-backed semantic
nodes through deterministic category orbits. Orbit position, force relaxation, density expansion,
camera state, minimap position, language, filters, and panel visibility are presentation only.
Distance, angle, animation, color intensity, and line curvature do not express ownership,
probability, guilt, identity attribution, or evidence strength.

Every node uses a circular category-specific vector icon and a human-readable title/subtitle.
Unreviewed candidates retain a dashed pending treatment. One-hop focus dims unrelated content;
edge labels appear only for selected or hovered context. Evidence, Navigation, and Review lenses
hide non-matching nodes and their edges without mutating the reducer output. The default right
inspector summarizes observed categories before exposing artifacts and provenance. Both sidebars
may be collapsed for graph inspection, and the EN/ID toggle changes interface copy only.
