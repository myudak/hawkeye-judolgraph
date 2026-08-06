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
selection, search, camera, and replay remains separate from stored graph truth. A continuous render
loop adds bounded force relaxation, glow, edge drawing, and relation particles. Pointer hit-testing
supports node selection and dragging; empty-space drag pans; wheel input zooms around the cursor.
`Fit`, search/focus, a camera-aware minimap, replay, pause, and speed controls never modify
persistent evidence.

The right inspector opens screenshot evidence and verified local artifact links for a saved case.
For an investigation it shows event-derived node state, fixture artifacts, the approval boundary,
and append-only human review. The bottom timeline is built from actual artifact timestamps or
persisted investigation events. Reduced-motion mode removes nonessential motion while preserving
the same information. A hidden accessible relationship list is the canvas equivalent of the
relationship table.

Alternate screenshot views stay grouped behind the canonical screenshot node and every verified
artifact remains available in the inspector. Investigation graphs continue to use meaningful
event-reduced entities. No event, HTTP request, font, script, or animation callback becomes graph
truth.
