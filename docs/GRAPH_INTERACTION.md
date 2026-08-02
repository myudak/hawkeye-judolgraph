# Progressive Graph Interaction

The graph reducer consumes stored events in sequence and ignores duplicate event IDs. Persistent
nodes and edges never depend on animation callbacks. The separate queue supports `spawn-node`,
`draw-edge`, `pulse-node`, and `focus-node`.

Primary nodes are seed or collected public pages, claimed brands, public contacts, external or
redirect destinations, and candidate domains. Artifact and request detail stays in inspectors and
the timeline. Observed relationships are solid, candidate assertions dashed, verified assertions
solid emphasized, and rejected assertions hidden by default while their events remain auditable.
Uncollected search leads remain visually distinct from collected pages.

The localhost MVP view provides progressive polling, stable graph table, causal path table,
evidence inspector, event timeline, search/focus filter, compact minimap, and system reduced-motion
support. Replay is the same idempotent reduction used for the live view.

