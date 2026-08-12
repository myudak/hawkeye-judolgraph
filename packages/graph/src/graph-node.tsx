import type { PointerEvent } from "react";
import type { EvidenceNodeData } from "./types";

const glyphs = {
  domain: "◎",
  page: "▤",
  telegram: "↗",
  phone: "☎",
  whatsapp: "◉",
};

export function GraphNode({
  node,
  selected,
  onSelect,
  onDragStart,
}: {
  node: EvidenceNodeData;
  selected: boolean;
  onSelect: () => void;
  onDragStart: (event: PointerEvent<SVGGElement>) => void;
}) {
  return (
    <g
      className="evidence-node"
      data-kind={node.kind}
      data-state={node.state}
      data-selected={selected}
      transform={`translate(${node.x} ${node.y})`}
      role="button"
      aria-label={`${node.label}, ${node.detail}, ${node.state}`}
      tabIndex={0}
      onClick={onSelect}
      onKeyDown={(event) =>
        (event.key === "Enter" || event.key === " ") && onSelect()
      }
      onPointerDown={onDragStart}
    >
      <circle
        r={node.kind === "domain" ? 32 : 25}
        className="evidence-node__halo"
      />
      <circle
        r={node.kind === "domain" ? 25 : 20}
        className="evidence-node__disc"
      />
      <text
        className="evidence-node__glyph"
        textAnchor="middle"
        dominantBaseline="central"
      >
        {glyphs[node.kind]}
      </text>
      <text
        className="evidence-node__label"
        y={node.kind === "domain" ? 48 : 40}
        textAnchor="middle"
      >
        {node.label}
      </text>
      <text
        className="evidence-node__detail"
        y={node.kind === "domain" ? 65 : 56}
        textAnchor="middle"
      >
        {node.detail}
      </text>
    </g>
  );
}
