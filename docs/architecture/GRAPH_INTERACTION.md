# Progressive Graph Interaction

The graph reducer consumes stored events in sequence and ignores duplicate event IDs. Persistent
nodes and edges never depend on animation callbacks. The separate queue supports `spawn-node`,
`draw-edge`, `pulse-node`, and `focus-node`.

Primary nodes are seed or collected public pages, claimed brands, public contacts, external or
redirect destinations, and candidate domains. Artifact and request detail stays in inspectors and
the timeline. Observed relationships are solid, candidate assertions dashed, verified assertions
solid emphasized, and rejected assertions hidden by default while their events remain auditable.
Uncollected search leads remain visually distinct from collected pages.

The localhost MVP view uses a DPR-aware two-dimensional canvas. Browser state for nodes, edges,
selection, search, camera, and replay remains separate from stored graph truth. Graph V2 places the
investigated site at the center and uses deterministic semantic orbits for captured pages, contacts,
brands, payments, offers, external destinations, pending candidates, and other observations. The
layout expands dense sectors without treating spatial proximity as evidence. Circular canvas nodes
use category-specific vector icons; no text glyph is used as an entity icon.

A continuous render loop adds bounded force relaxation and restrained state motion. Pointer
hit-testing supports node selection and dragging; empty-space drag pans; wheel input zooms around
the cursor. Selection applies one-hop focus, while unrelated nodes and edges are dimmed rather than
deleted. Relation labels and direction markers appear only in the selected or hovered context.
`Fit`, search/focus, a camera-aware minimap, replay, pause, and speed controls never modify
persistent evidence. Evidence, Navigation, and Review lenses are visibility projections only; the
Review lens does not upgrade a candidate into a verified relation.

The product has three explicit views: a start form with recent cases and guided/capture-only modes;
the canvas workspace; and a printable investigation summary with scope, pages, candidates, review
state, chronology, artifact manifest, and Markdown/JSON/ZIP exports. The right workspace inspector
defaults to a compact categorized inventory of claimed brands, public contacts, links/destinations,
payment observations, offer claims, and pending candidates. The Evidence tab opens screenshot
evidence and verified local artifact links for a saved case.

For an investigation the inspector shows event-derived node state, fixture artifacts, the approval
boundary, and append-only human review. Both side panels can be collapsed independently without
changing selection or graph truth. The bottom replay bar separates transport controls, the current
event, the event trail, and temporal navigation. It is built from actual artifact timestamps or
persisted investigation events. Reduced-motion mode removes nonessential motion while preserving
the same information. A hidden interactive semantic node list and relationship list are the
accessible canvas equivalents.

Alternate screenshot views stay grouped behind the canonical screenshot node and every verified
artifact remains available in the inspector. Investigation graphs continue to use meaningful
event-reduced entities. No event, HTTP request, font, script, or animation callback becomes graph
truth.
