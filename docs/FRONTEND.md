# HAWK-EYE frontend boundary

The competition console uses React 19, TypeScript, Vite, Tailwind CSS v4, and the checked-in
shadcn/ui preset. It is a presentation adapter over the existing localhost FastAPI application.
It does not define evidence truth, collection policy, graph reduction, candidate state, assertion
meaning, or review history.

## Routes

- `#/` starts one bounded public investigation and lists saved cases/runs.
- `#/scan/{job_id}` polls the persisted job projection and displays real stages without inventing
  a completion percentage.
- `#/workspace/{case|run}/{id}` combines the semantic graph, evidence inspector, filters, and event
  replay.
- `#/summary/{case|run}/{id}` produces a human-readable report from the same verified source.

Hash routing keeps every browser route on the loopback index document. All data and artifact links
remain same-origin `/api/...` requests. There is no remote preview, iframe, external navigation,
or application-level raw HTML injection.

## Truth and projection rules

The frontend narrows every source into either `CaseDetails` or `RunDetails` before rendering. A
run may reference a verified source case, but the two response shapes are not merged or rewritten.
The graph view model maps persisted node/observation categories to presentation-only visual kinds:

```text
Page · Contact · Brand · Transaction · Offer · Destination · Candidate · Other
```

Unknown categories deterministically resolve to `Other`. Filtering hides nodes and associated
edges without changing stored coordinates or backend graph data. Animation, minimap state, search,
selection, and replay are UI state only. Screenshot, HTML, visible-text, readiness, and interaction
artifacts remain in the evidence inspector instead of becoming graph nodes.

Graph V2 uses a centered investigated-site node, density-aware semantic orbits, circular vector
icons, contextual relation labels, and one-hop focus. Evidence, Navigation, and Review lenses only
select truthful subsets of the same projection. The two side panels are independently collapsible;
full-canvas mode is still the same evidence state. The inspector opens on a categorized observation
summary and keeps provenance, screenshots, artifacts, technical state, and human review in their
dedicated tabs.

The workspace shell supports English and Indonesian presentation copy through a local EN/ID
toggle. Persisted evidence values, URLs, event kinds, identifiers, and reviewer records are never
translated or rewritten. The language preference is local browser presentation state, not part of
the case package.

Candidates always display relationship-neutral language. Verification emphasis is derived only
from persisted review/assertion state. Judol indication is an integer count of classified evidence
items with provenance; the interface does not derive a probability or percentage.

## Production build

From the repository root:

```powershell
pnpm install --frozen-lockfile
pnpm check:web
pnpm build
```

The Vite build empties and recreates
`apps/api/src/hawkeye/review_app/static/`. That directory is generated and ignored by Git, but is
included in the Python wheel after `pnpm package`. The entry file and stylesheet use stable names
(`app.js`, `styles.css`); lazily loaded route chunks are content-hashed beneath `static/chunks/`.
FastAPI continues to set the self-only content security policy and serve the result only on
loopback.

## Accessibility and motion

Interactive graph nodes have a parallel semantic list, evidence selection works in both
directions, timeline markers expose their current state, and focus styles are retained. At narrow
viewports the three-panel workspace becomes a scrollable document. `prefers-reduced-motion`
disables decorative animation while preserving investigation state.
