import type { EvidenceEdgeData, EvidenceNodeData } from "./types";

export function GraphEdge({
  edge,
  source,
  target,
}: {
  edge: EvidenceEdgeData;
  source: EvidenceNodeData;
  target: EvidenceNodeData;
}) {
  const midX = (source.x + target.x) / 2;
  const midY = (source.y + target.y) / 2;
  const bend = Math.abs(source.x - target.x) > 180 ? -34 : 18;
  const path = `M ${source.x} ${source.y} Q ${midX} ${midY + bend} ${target.x} ${target.y}`;
  return (
    <g
      className="evidence-edge"
      data-state={edge.state}
      data-kind={target.kind}
    >
      <path d={path} className="evidence-edge__halo" />
      <path d={path} className="evidence-edge__line" pathLength="1" />
      <text x={midX} y={midY + bend / 2 - 6} textAnchor="middle">
        {edge.label}
      </text>
    </g>
  );
}
