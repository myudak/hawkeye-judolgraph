export interface ForceNode {
  id: string;
  x: number;
  y: number;
  tx: number;
  ty: number;
  vx: number;
  vy: number;
  pinned: boolean;
  radius?: number;
  primary?: boolean;
}

export interface ForceEdge {
  source: string;
  target: string;
}

function phaseFor(id: string) {
  let hash = 2166136261;
  for (const character of id) {
    hash ^= character.charCodeAt(0);
    hash = Math.imul(hash, 16777619);
  }
  return ((hash >>> 0) / 0xffffffff) * Math.PI * 2;
}

export function applyMagneticForces<TNode extends ForceNode>(options: {
  nodes: TNode[];
  edges: ForceEdge[];
  time: number;
  delta: number;
  reducedMotion: boolean;
  nodeById: (id: string) => TNode | undefined;
}) {
  const { nodes, edges, time, reducedMotion, nodeById } = options;
  const step = Math.min(2, Math.max(0.35, options.delta / 16.667));

  for (const node of nodes) {
    if (node.pinned) continue;
    const phase = phaseFor(node.id);
    const ambient = reducedMotion ? 0 : node.primary ? 4 : 19;
    const anchorX = node.tx + Math.cos(time * 0.00072 + phase) * ambient;
    const anchorY = node.ty + Math.sin(time * 0.00061 + phase * 1.31) * ambient;
    node.vx += (anchorX - node.x) * (node.primary ? 0.024 : 0.0085) * step;
    node.vy += (anchorY - node.y) * (node.primary ? 0.024 : 0.0085) * step;
  }

  for (let leftIndex = 0; leftIndex < nodes.length; leftIndex += 1) {
    const left = nodes[leftIndex];
    for (
      let rightIndex = leftIndex + 1;
      rightIndex < nodes.length;
      rightIndex += 1
    ) {
      const right = nodes[rightIndex];
      const dx = right.x - left.x;
      const dy = right.y - left.y;
      const distance = Math.max(1, Math.hypot(dx, dy));
      const minimum = (left.radius ?? 28) + (right.radius ?? 28) + 62;
      const range = Math.max(minimum, 185);
      if (distance > range) continue;
      const repulsion = ((range - distance) / range) * 0.78 * step;
      if (!left.pinned) {
        left.vx -= (dx / distance) * repulsion;
        left.vy -= (dy / distance) * repulsion;
      }
      if (!right.pinned) {
        right.vx += (dx / distance) * repulsion;
        right.vy += (dy / distance) * repulsion;
      }
    }
  }

  for (const edge of edges) {
    const source = nodeById(edge.source);
    const target = nodeById(edge.target);
    if (!source || !target) continue;
    const dx = target.x - source.x;
    const dy = target.y - source.y;
    const distance = Math.max(1, Math.hypot(dx, dy));
    const anchorDistance = Math.max(
      112,
      Math.hypot(target.tx - source.tx, target.ty - source.ty),
    );
    const extension = distance - anchorDistance;
    const spring = extension * 0.018 * step;
    if (!source.pinned && !source.primary) {
      source.vx += (dx / distance) * spring;
      source.vy += (dy / distance) * spring;
    }
    if (!target.pinned && !target.primary) {
      target.vx -= (dx / distance) * spring;
      target.vy -= (dy / distance) * spring;
    }
  }

  for (const node of nodes) {
    if (node.pinned) continue;
    node.vx *= Math.pow(node.primary ? 0.76 : 0.91, step);
    node.vy *= Math.pow(node.primary ? 0.76 : 0.91, step);
    const speed = Math.hypot(node.vx, node.vy);
    if (speed > 24) {
      node.vx = (node.vx / speed) * 24;
      node.vy = (node.vy / speed) * 24;
    }
    node.x += node.vx * step;
    node.y += node.vy * step;
  }
}

export function releaseWithMomentum(node: ForceNode) {
  node.pinned = false;
  node.vx += (node.tx - node.x) * 0.11;
  node.vy += (node.ty - node.y) * 0.11;
}
