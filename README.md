# JudolGraph / HAWK-EYE

Engine V1 turns one public seed URL into an auditable, local evidence graph and a deterministic set
of pending candidate hosts. It can compare two already-collected local cases without revisiting
either domain, optionally query one bounded public-source strategy for additional pending leads,
and present verified local evidence in a localhost-only investigator console. Collection performs a
same-site breadth-first crawl at depth zero and one only (five HTML pages maximum). It does not use
AI extraction, make legal conclusions, log in, submit forms, bypass restrictions, or automatically
browse generated candidates.

## Setup

Use Python 3.12 or newer, then install the package and Chromium runtime:

```powershell
python -m pip install -e ".[dev]"
python -m playwright install chromium
```

## Investigate one public URL

```powershell
python -m hawkeye investigate https://example.com --output ./cases --timeout 30
```

Optional collection controls are `--case-id`, `--max-redirects`, `--max-pages` (1–5),
`--max-depth` (0–1), `--case-timeout` (up to 120 seconds), `--user-agent`, and `--headed`.
The hard defaults are depth one, five pages, five redirects per page, 30 seconds per page, one
browser page at a time, 120 seconds per case, 200 browser requests per case, 10 MB of declared
response bodies per case, and a 2 MB rendered-HTML limit per page. Public document navigation is
limited to default HTTP/HTTPS ports (80/443); custom ports are permitted only for explicit
loopback fixture tests.

By default, V0.2 compares usable evidence with completed sibling cases below `--output`. Supply
`--corpus <path>` to use a different local case root. Corpus reading is local only: malformed,
incomplete, failed, restricted, or candidate-output artifacts are ignored.

Unsafe schemes, loopback/private/link-local addresses, localhost, cloud metadata endpoints, and
redirects to those destinations are rejected by default. The request guard re-resolves and
validates every routed document, script, image, stylesheet, iframe, and fetch/XHR request. Service
workers and WebSockets are disabled; unexpected popups are closed and downloads are not accepted.

The output is a case directory with:

```text
case.json
pages/page-001.html
screenshots/page-001.png
network/page-001-redirects.json (when a document redirect is observed)
evidence.json
entities.json
candidates.json
candidate_observations.json
graph.json
pages.json
frontier.json
run.log
```

`graph.json` keeps structural relationships separate from extracted relationships. Every extracted
relationship points to its source evidence record, source URL, extraction method, and confidence.

`pages.json` is the per-page crawl audit: depth, parent page, source evidence ID, original anchor,
normalised URL, result, and any blocked browser request. `frontier.json` records every observed
anchor's deterministic state (`discovered`, `queued`, `visiting`, `completed`, `skipped`, or
`failed`) and the reason it was not crawled when applicable. Each child page is linked in
`graph.json` by an evidence-backed `discovered_via_link` edge carrying the original href, anchor
text, normalized target, and depth.

Every observed document-navigation redirect is saved under `network/` as a hashed `network_event`
evidence record. When a child-page redirect is stopped because it is external or unsafe, its
destination also appears as a skipped `redirect` entry in `frontier.json`, without navigating that
destination.

## Candidate generation (V0.2)

`candidates.json` contains only relationship-neutral, `pending` candidate hosts. A candidate is
generated from an evidence-backed external anchor or a top-level document redirect, or when usable
current and historical local cases share a Telegram handle, WhatsApp/phone identifier, referral
code, or exact asset URL. `candidate_observations.json` retains immutable accepted and excluded
observations; each candidate reason lists both sides' supporting evidence IDs, globally unambiguous
`case_id`/`evidence_id`/`observation_id` references, source URLs, and local-corpus
frequency/case/domain counts.

Candidate identity is the normalized observed hostname, with registrable-domain and public/private
suffix classification retained for grouping. This preserves a lead such as `backup.example.com`
when the seed is `www.example.com`, while still marking it as a same-registrable-domain external
host. IP literals, public-suffix-only values, malformed URLs, and an already-observed source host
are excluded rather than promoted. Common asset/CDN/analytics providers, generic referral values,
ubiquitous external references, and signals seen across more than three corpus domains are retained
as excluded observations to avoid turning commodity infrastructure into leads. Exact asset URLs
sort query parameters but keep every parameter/value; raw and canonical forms are stored.

Each candidate document records the completed-case corpus snapshot (`case_ids`, a deterministic
manifest hash, timestamp, and visible exclusions) used for its local comparisons. Historical source
entities are accepted only when their referenced HTML artifact stays inside the case directory and
matches its recorded SHA-256; malformed, incomplete, or modified corpus entries are listed as
excluded rather than silently trusted. `schema_version` and `scoring_policy_version` are persisted.
Scores are discovery priorities only, capped at 100 and calculated from unique reason types; all
distinct observed signal values remain in the output. They do not state that two domains are
mirrors, share an owner, or should be crawled.

## Offline domain comparison (V0.3)

Compare two completed case directories using only the artifacts already stored on disk:

```powershell
python -m hawkeye compare ./cases/case-a ./cases/case-b --output ./comparisons/case-a--case-b.json
```

The resulting `comparison.json` provides separately evidence-backed component scores for shared
Telegram/WhatsApp/referral entities, visible text, DOM structure, screenshot perceptual hash, and
exact shared asset URLs. It combines those fixed weights into a `candidate_mirror_score` while
always keeping `review_status: needs_review`; it never asserts common ownership, an exact mirror,
or wrongdoing. Every component names the verified source artifact hashes it used, and matching
entity references include both the case and evidence ID.

The comparison command performs no DNS resolution, HTTP request, browser launch, or candidate
navigation. It reads only `case.json`, `pages.json`, `evidence.json`, `entities.json`, and the
hashed HTML/screenshot artifacts they reference. Missing, escaped, or modified artifacts are
rejected instead of being compared. It persists the comparator version, scoring policy, fixed
weights, and deterministic manifests of those exact inputs; it rejects a duplicate case or an
identical case manifest.

Each component is explicitly `scored`, `low_information`, or `not_applicable`. Empty signal sets
never score as a match; generic referral values and common CDN assets use the V0.2 suppression
policy. For multi-page cases, duplicate HTML is used once, pages are paired in stable order, and an
unmatched page contributes zero rather than being silently discarded. The output retains every
page-pair score. HTML is decoded from its verified bytes, and screenshots must be bounded PNGs
whose stored dimensions match the capture metadata. Near-uniform screenshots and sparse text/DOM
evidence remain visible as low-information instead of inflating the score.

The same-site boundary is exact, not wildcard-based: after the seed completes, only the validated
seed hostname and the validated final canonical hostname reached by its safe redirect are eligible
for navigation. External domains remain observable as extracted evidence and frontier decisions,
but are never crawled. An external redirect from a child page is stopped and recorded.

## External discovery (V0.4)

V0.4 has one isolated, opt-in strategy: a bounded search of existing public `urlscan.io` website
scan records for the completed case hostname. It never submits a scan, follows a source redirect,
or opens any URL returned by the source. It writes a new output directory containing the raw JSON
response, its separate metadata record, and an evidence-backed `external-discovery.json` with
pending leads only:

```powershell
python -m hawkeye discover ./cases/case-a `
  --source urlscan-public `
  --output ./external-discovery/case-a-urlscan `
  --limit 10 `
  --timeout 10
```

An optional `--urlscan-api-key` is passed only in the request header and is never stored or printed.
The source requires a public registrable case hostname, evaluates no more than 20 result rows, uses
a ten-second ceiling, blocks redirects, ignores proxy configuration, bounds the JSON response to
1 MB, validates an exact `https://urlscan.io` endpoint contract before a live request, and uses the
same fail-closed DNS policy as collection. Each run persists `source-response.json`,
`source-response.meta.json`, the exact request URL (without credentials), raw-response SHA-256,
collection time, response byte count, HTTP status where available, result limit, input `case.json`
hash, every accepted or excluded observed URL, and source-result IDs. `external-candidates.json`
and `external-candidate-observations.json` reuse the V0.2 candidate schema, normalization,
deduplication, and priority calculation; an external record gets only a low, standalone discovery
reason and remains `pending` with `relationship: null`. Returned domains are **not** fed back into
the browser collector.

For deterministic CI or offline review, replay a saved URLScan search payload without network
access:

```powershell
python -m hawkeye discover ./cases/case-a `
  --output ./external-discovery/case-a-fixture `
  --response-file ./tests/fixtures/urlscan_public_response.json
```

Like Chromium collection, the standard-library HTTP client resolves the fixed hostname separately
after the preflight DNS validation. The endpoint is fixed, HTTPS-only, redirect-free, proxy-free,
and validated before each live request, but complete DNS-rebinding elimination would still require
network-layer IP pinning or a validating proxy. This residual TOCTOU limitation is documented
rather than hidden.

## Investigator console (V1)

The V1 console is a local, read-only evidence browser—not a crawler, review workflow, or deployment
service. It intentionally binds only to `127.0.0.1`, has no `--host` option, accepts only the
`127.0.0.1` and `localhost` Host headers (and ignores forwarded-host headers), has no CORS
middleware, no write endpoints, no remote favicon/preview loading, and no candidate-domain DNS or
HTTP access:

```powershell
python -m hawkeye serve --cases ./cases --port 8760
```

Open `http://127.0.0.1:8760` locally. The server accepts opaque case and evidence IDs only; it
never accepts a filesystem path from a request. Before a case is displayed, it verifies completion
state, JSON schemas, unique IDs, graph/candidate evidence references, safe path containment,
symlink/junction rejection, artifact byte limits, SHA-256 values, UTF-8 HTML, JSON network events,
and bounded PNG screenshots. A failed check yields an integrity error rather than a partial case.

Screenshots are the only evidence shown inline. Captured HTML is delivered as a `text/plain`
attachment with `Content-Disposition: attachment`, never inserted into the application DOM or an
iframe. The UI uses a strict self-only CSP, local assets, `textContent` rendering, and redacted
display representations for credentialed URLs, sensitive query values, referral values, and phone
numbers. Candidate hosts are inert text with `pending` status and `relationship: null`; a priority
or V0.3 score never becomes a mirror/ownership conclusion.

This is suitable for one local investigator on the same machine. Binding beyond loopback, adding
multiple users, or adding review notes/exports requires authentication, authorization, separate
application state, and a deployment security review; those features are intentionally absent.

## Explicit V0.2 policy limits

The collector does not fetch or interpret `robots.txt` in this bounded local-engine milestone; any
deployment must set its own authority and robots policy before collection. It revalidates DNS at
each intercepted request and caps each resolver call at five seconds, but Chromium independently
performs its own hostname resolution after that check. A validating proxy or IP pinning is required
to fully eliminate DNS-rebinding TOCTOU risk, so V0.2 records this as a residual limitation rather
than claiming complete SSRF immunity.

Byte budgeting uses response `Content-Length` headers plus the rendered-HTML cap. Chunked or
otherwise undeclared response bodies cannot be pre-bounded by Playwright alone; a production proxy
would be needed for strict wire-byte enforcement.

Each `case.json` distinguishes whether the browser captured a document (`navigation_status`) from
what was captured (`capture_outcome`) and whether it is usable as target-site evidence
(`content_usable`). The fixed outcomes are `content`, `unavailable_page`, `bot_challenge`,
`geo_restricted`, `consent_wall`, `navigation_error`, `timeout`, and `unknown_restriction`.
Restricted pages still retain their HTML and screenshot, but their page content is not used to
create target-content entities or graph relationships.

## Tests and checks

```powershell
pytest
ruff format --check .
ruff check .
mypy hawkeye
```

The end-to-end fixture test uses an explicit loopback-only test policy. The normal CLI rejects
loopback targets; `--allow-loopback-for-testing` exists only so a local fixture server can exercise
the exact CLI path. It additionally requires `HAWKEYE_TEST_MODE=1`, and never enables arbitrary
private or cloud-metadata destinations.

## Bounded live robustness check

After fixture checks pass, run the fixed ten-domain matrix:

```powershell
python -m hawkeye smoke-test --output ./live-smoke-tests
```

It deliberately uses `max_pages=1` and `max_depth=0` for each target, follows at most five
redirects, uses a fresh browser context for each attempt, records failures/restrictions, and
continues through the matrix without interacting with pages. It is a landing-page robustness check,
not a recursive live crawl.
