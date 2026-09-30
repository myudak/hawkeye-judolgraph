# Backend-free interactive demo

The demo reuses the investigator UI with a build-selected local data adapter. It requires no
Python runtime, collector, API, database, account, or model key. It only accepts the three supplied
fictional scenarios from the dropdown; it cannot investigate arbitrary URLs.

## Run and build

Requirements for building: Node.js 22.13+ and pnpm 11.3+.

```bash
pnpm install --frozen-lockfile
pnpm dev:demo
```

To produce and inspect the deployable files:

```bash
pnpm build:demo
pnpm preview:demo
```

Publish the contents of `apps/web/dist-demo/` to a static host. A host that builds from Git should
use the repository root as its working directory, `pnpm build:demo` as its build command, and
`apps/web/dist-demo` as its publish directory. No server entrypoint or environment secrets are
needed. Hash-based routes and relative assets support deployment below a subdirectory.

The existing root `vercel.json` builds the marketing site. Configure a separate demo deployment
with the settings above; the marketing deployment is not replaced by this feature.

This is a static web application, not an installed offline PWA. It still needs a static HTTP host
for first load and for uncached route chunks. An ordinary local static server can host the downloaded
build without internet access; opening `index.html` through `file://` is not supported.

## Scenarios and flow

| Scenario | Demonstrated boundary |
| --- | --- |
| Public contact trail | Two fictional pages, a visible email, an authored offer indicator, source screenshots, and provenance. |
| Related-site review | A direct public link remains a pending lead. Approval reveals one bundled candidate page; a reviewer can assess a `publicly_links_to` assertion. No ownership inference is made. |
| Limited capture | A restriction screenshot is preserved while contacts, offers, and relationships remain absent. |

Start demo plays an accelerated six-second capture sequence, then offers the existing workspace.
The three-step guide points to the timeline, evidence inspector, and summary. Saved sample cases
can also be opened directly. Markdown and JSON reports are generated in the browser and explicitly
identify sample data; ZIP export and provider settings are unavailable in this mode.

Playback progress, approval, and up to 50 review versions persist in `sessionStorage` across reloads
in the same tab. Reset demo clears sample progress and review state. State is separate from live
investigations; no review is sent to a server. If session storage is unavailable, sample changes
remain in memory until reload.

## Source and verification

`apps/web/src/demo/fixtures.json` contains authored synthetic case/run state. The matching source
HTML is stored as inert `.html.txt`, with visible text and PNG screenshots in `src/demo/assets`.
All example sites and contacts use `.invalid` domains. Fixture artifacts include SHA-256 hashes;
automated tests check the hashes, observation sources, and graph/event references. These examples
are demonstration material, not live captures or research benchmark results.

Regenerating fixtures is an optional development task, requiring the repository's locked Python
development dependencies and Playwright Chromium:

```bash
pnpm setup
uv run python tools/demo/build_fixtures.py
pnpm --filter @hawkeye/web exec prettier --write src/demo/fixtures.json
```

The generator renders local authored HTML and aborts all page network requests. Regeneration is
not part of a static deployment build. The regular live build selects `api/live-client.ts` and
does not bundle demo fixtures; the demo build selects `demo/client.ts` and does not bundle the live
HTTP client.

```bash
pnpm check
pnpm verify:demo
```

Browser verification serves only the static build under `/hawkeye-demo/`, rejects API and external
requests, and checks all scenarios, reload, source screenshots, approval/review/reset, exports,
unknown routes, themes, Indonesian copy, and mobile layout. Its screenshots remain ignored under
`verification-output/static-demo/`. CI runs this verification after the complete core gate.

The optional GEMASTIK submission archive is excluded from public checkouts. Its existing tests run
when `competition/gemastik-2026/` is present and report explicit skips otherwise; historical
evaluation inputs and results remain unchanged.
