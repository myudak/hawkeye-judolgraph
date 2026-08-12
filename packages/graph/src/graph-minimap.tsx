import type { EvidenceNodeData } from "./types";

export function GraphMinimap({ nodes }: { nodes: EvidenceNodeData[] }) {
  return (
    <svg
      className="graph-minimap"
      viewBox="0 0 760 520"
      role="img"
      aria-label="Graph minimap"
    >
      <rect x="8" y="8" width="744" height="504" rx="18" />
      {nodes.map((node) => (
        <circle
          key={node.id}
          cx={node.x}
          cy={node.y}
          r={node.kind === "domain" ? 13 : 8}
          data-state={node.state}
        />
      ))}
      <rect
        className="graph-minimap__viewport"
        x="95"
        y="70"
        width="560"
        height="370"
        rx="8"
      />
    </svg>
  );
}
