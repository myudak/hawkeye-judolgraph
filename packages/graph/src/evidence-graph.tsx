import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  useSyncExternalStore,
  type PointerEvent,
  type WheelEvent,
} from "react";
import { demoEdges, demoNodes } from "./data";
import {
  CornersOutIcon,
  MagnifyingGlassMinusIcon,
  MagnifyingGlassPlusIcon,
} from "@phosphor-icons/react";
import { GraphLegend } from "./graph-legend";
import { drawOfficialSocialIcon } from "./canvas-icons";
import { applyMagneticForces, releaseWithMomentum } from "./force-simulation";
import type { EvidenceKind, EvidenceNodeData } from "./types";

interface SimNode extends EvidenceNodeData {
  x: number;
  y: number;
  tx: number;
  ty: number;
  vx: number;
  vy: number;
  pinned: boolean;
  bornAt: number;
  radius: number;
  primary: boolean;
}

interface Camera {
  x: number;
  y: number;
  zoom: number;
  targetX: number;
  targetY: number;
  targetZoom: number;
}

interface PointerState {
  id: number;
  startX: number;
  startY: number;
  cameraX: number;
  cameraY: number;
  dragId?: string;
  moved: boolean;
}

const colors: Record<string, string> = {
  seed: "#ef467f",
  page: "#5b91ef",
  contact: "#27c5ba",
  pending: "#9b7dde",
  rejected: "#9b687c",
};

type GraphLanguage = "id" | "en";

function readLanguage(): GraphLanguage {
  if (typeof document === "undefined") return "id";
  return document.documentElement.dataset.language === "en" ? "en" : "id";
}

function subscribeLanguage(onChange: () => void) {
  if (typeof document === "undefined") return () => undefined;
  const observer = new MutationObserver(onChange);
  observer.observe(document.documentElement, {
    attributes: true,
    attributeFilter: ["data-language"],
  });
  return () => observer.disconnect();
}

function localizedNode(node: EvidenceNodeData, language: GraphLanguage) {
  if (language === "en") return node;
  const detail: Record<EvidenceNodeData["id"], string> = {
    seed: "Domain publik yang diselidiki",
    contact: "Halaman yang dipreservasi",
    telegram: "Akun Telegram",
    phone: "Nomor telepon publik",
    whatsapp: "Identitas WhatsApp",
    candidate: "Domain kandidat",
    rejected: "Relasi ditolak",
  };
  const source: Record<EvidenceNodeData["id"], string> = {
    seed: node.source,
    contact: node.source,
    telegram: "Teks terlihat pada /Contact",
    phone: "Teks terlihat pada /Contact",
    whatsapp: "Rute kontak publik",
    candidate: "Identitas publik yang sama",
    rejected: "Keputusan tinjauan manusia",
  };
  return {
    ...node,
    detail: detail[node.id] ?? node.detail,
    source: source[node.id] ?? node.source,
  };
}

function rgba(hex: string, alpha: number) {
  const clean = hex.replace("#", "");
  const value = Number.parseInt(clean, 16);
  return `rgba(${(value >> 16) & 255}, ${(value >> 8) & 255}, ${value & 255}, ${alpha})`;
}

function nodeColor(node: EvidenceNodeData) {
  if (node.state === "pending") return colors.pending;
  if (node.state === "rejected") return colors.rejected;
  if (node.id === "seed") return colors.seed;
  if (node.kind === "page") return colors.page;
  return colors.contact;
}

function nodeRadius(node: EvidenceNodeData) {
  if (node.id === "seed") return 34;
  if (node.kind === "domain") return 27;
  return 24;
}

function drawIcon(
  context: CanvasRenderingContext2D,
  kind: EvidenceKind,
  x: number,
  y: number,
  size: number,
  color: string,
) {
  const s = size;
  if (kind === "telegram" || kind === "whatsapp") {
    drawOfficialSocialIcon(context, kind, x, y, s * 2);
    return;
  }
  context.save();
  context.translate(x, y);
  context.strokeStyle = color;
  context.lineWidth = Math.max(1.3, s * 0.1);
  context.lineCap = "round";
  context.lineJoin = "round";
  context.beginPath();
  if (kind === "domain") {
    context.arc(0, 0, s * 0.68, 0, Math.PI * 2);
    context.moveTo(-s * 0.66, 0);
    context.lineTo(s * 0.66, 0);
    context.moveTo(0, -s * 0.66);
    context.bezierCurveTo(
      -s * 0.36,
      -s * 0.35,
      -s * 0.36,
      s * 0.35,
      0,
      s * 0.66,
    );
    context.moveTo(0, -s * 0.66);
    context.bezierCurveTo(s * 0.36, -s * 0.35, s * 0.36, s * 0.35, 0, s * 0.66);
  } else if (kind === "page") {
    context.roundRect(-s * 0.53, -s * 0.67, s * 1.06, s * 1.34, s * 0.12);
    for (const offset of [-0.3, 0, 0.3]) {
      context.moveTo(-s * 0.3, offset * s);
      context.lineTo(s * 0.28, offset * s);
    }
  } else {
    context.moveTo(-s * 0.5, -s * 0.55);
    context.quadraticCurveTo(-s * 0.68, -s * 0.38, -s * 0.46, s * 0.04);
    context.quadraticCurveTo(-s * 0.09, s * 0.62, s * 0.43, s * 0.55);
    context.quadraticCurveTo(s * 0.66, s * 0.5, s * 0.5, s * 0.22);
    context.lineTo(s * 0.25, 0);
    context.quadraticCurveTo(s * 0.08, s * 0.16, -s * 0.1, -s * 0.04);
    context.lineTo(-s * 0.3, -s * 0.3);
    context.closePath();
  }
  context.stroke();
  context.restore();
}

function edgeControl(a: SimNode, b: SimNode, bend: number) {
  const dx = b.x - a.x;
  const dy = b.y - a.y;
  const length = Math.max(1, Math.hypot(dx, dy));
  return {
    x: (a.x + b.x) / 2 + (-dy / length) * bend,
    y: (a.y + b.y) / 2 + (dx / length) * bend,
  };
}

function quadraticPoint(
  a: { x: number; y: number },
  control: { x: number; y: number },
  b: { x: number; y: number },
  t: number,
) {
  const inv = 1 - t;
  return {
    x: inv * inv * a.x + 2 * inv * t * control.x + t * t * b.x,
    y: inv * inv * a.y + 2 * inv * t * control.y + t * t * b.y,
  };
}

function createSimulation(nodes: EvidenceNodeData[]) {
  const now = performance.now();
  return new Map(
    nodes.map((node, index) => {
      const tx = node.x - 350;
      const ty = node.y - 260;
      return [
        node.id,
        {
          ...node,
          tx,
          ty,
          x: node.id === "seed" ? 0 : tx * 0.28,
          y: node.id === "seed" ? 0 : ty * 0.28,
          vx: 0,
          vy: 0,
          pinned: false,
          bornAt: now + index * 65,
          radius: nodeRadius(node),
          primary: node.id === "seed",
        } satisfies SimNode,
      ];
    }),
  );
}

export function EvidenceGraph({
  visibleStep = 4,
  compact = false,
  selectedId: controlledSelected,
  onSelectionChange,
}: {
  visibleStep?: number;
  compact?: boolean;
  selectedId?: string;
  onSelectionChange?: (node: EvidenceNodeData) => void;
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const minimapRef = useRef<HTMLCanvasElement>(null);
  const simulationRef = useRef<Map<string, SimNode>>(new Map());
  const sizeRef = useRef({ width: 900, height: 560 });
  const cameraRef = useRef<Camera>({
    x: 0,
    y: 0,
    zoom: 0.92,
    targetX: 0,
    targetY: 0,
    targetZoom: 0.92,
  });
  const pointerRef = useRef<PointerState | null>(null);
  const hoveredRef = useRef<string | null>(null);
  const selectedRef = useRef(controlledSelected ?? "seed");
  const reducedMotionRef = useRef(false);
  const [selected, setSelected] = useState(controlledSelected ?? "seed");
  const language = useSyncExternalStore(
    subscribeLanguage,
    readLanguage,
    () => "id",
  );
  const [hovered, setHovered] = useState<{
    node: EvidenceNodeData;
    x: number;
    y: number;
  } | null>(null);

  const nodes = useMemo(
    () => demoNodes.filter((node) => node.step <= visibleStep),
    [visibleStep],
  );
  const edges = useMemo(
    () => demoEdges.filter((edge) => edge.step <= visibleStep),
    [visibleStep],
  );
  const active =
    nodes.find((node) => node.id === (controlledSelected ?? selected)) ??
    nodes[0];

  useEffect(() => {
    const current = simulationRef.current;
    const incoming = createSimulation(nodes);
    for (const [id, node] of incoming) {
      const existing = current.get(id);
      if (existing)
        incoming.set(id, {
          ...node,
          x: existing.x,
          y: existing.y,
          vx: existing.vx,
          vy: existing.vy,
          pinned: existing.pinned,
          bornAt: existing.bornAt,
        });
    }
    simulationRef.current = incoming;
  }, [nodes]);

  useEffect(() => {
    if (controlledSelected) {
      selectedRef.current = controlledSelected;
      setSelected(controlledSelected);
    }
  }, [controlledSelected]);

  const selectNode = useCallback(
    (node: EvidenceNodeData) => {
      selectedRef.current = node.id;
      setSelected(node.id);
      onSelectionChange?.(node);
    },
    [onSelectionChange],
  );

  const fitView = useCallback(() => {
    const values = [...simulationRef.current.values()];
    if (!values.length) return;
    const minX = Math.min(...values.map((node) => node.tx));
    const maxX = Math.max(...values.map((node) => node.tx));
    const minY = Math.min(...values.map((node) => node.ty));
    const maxY = Math.max(...values.map((node) => node.ty));
    const width = Math.max(280, maxX - minX + 230);
    const height = Math.max(220, maxY - minY + 190);
    const size = sizeRef.current;
    const camera = cameraRef.current;
    camera.targetX = (minX + maxX) / 2;
    camera.targetY = (minY + maxY) / 2;
    camera.targetZoom = Math.max(
      0.52,
      Math.min(1.12, Math.min(size.width / width, size.height / height)),
    );
  }, []);

  useEffect(() => {
    const container = containerRef.current;
    const canvas = canvasRef.current;
    const minimap = minimapRef.current;
    if (!container || !canvas || !minimap) return;
    reducedMotionRef.current = window.matchMedia(
      "(prefers-reduced-motion: reduce)",
    ).matches;
    const resize = () => {
      const bounds = container.getBoundingClientRect();
      const width = Math.max(320, Math.floor(bounds.width));
      const height = Math.max(compact ? 500 : 560, Math.floor(bounds.height));
      const dpr = Math.min(2, window.devicePixelRatio || 1);
      sizeRef.current = { width, height };
      canvas.width = Math.floor(width * dpr);
      canvas.height = Math.floor(height * dpr);
      const miniBounds = minimap.getBoundingClientRect();
      minimap.width = Math.max(1, Math.floor(miniBounds.width * dpr));
      minimap.height = Math.max(1, Math.floor(miniBounds.height * dpr));
      fitView();
    };
    resize();
    const observer = new ResizeObserver(resize);
    observer.observe(container);
    return () => observer.disconnect();
  }, [compact, fitView]);

  useEffect(() => {
    const canvas = canvasRef.current;
    const minimap = minimapRef.current;
    if (!canvas || !minimap) return;
    const context = canvas.getContext("2d", { alpha: true });
    const mini = minimap.getContext("2d", { alpha: true });
    if (!context || !mini) return;
    let frame = 0;
    let last = performance.now();

    const paint = (time: number) => {
      const delta = Math.min(32, Math.max(1, time - last));
      last = time;
      const dpr = Math.min(2, window.devicePixelRatio || 1);
      const { width, height } = sizeRef.current;
      const camera = cameraRef.current;
      const sim = simulationRef.current;
      camera.x += (camera.targetX - camera.x) * 0.12;
      camera.y += (camera.targetY - camera.y) * 0.12;
      camera.zoom += (camera.targetZoom - camera.zoom) * 0.12;

      const values = [...sim.values()];
      applyMagneticForces({
        nodes: values,
        edges,
        time,
        delta,
        reducedMotion: reducedMotionRef.current,
        nodeById: (id) => sim.get(id),
      });

      const screen = (node: SimNode) => ({
        x: (node.x - camera.x) * camera.zoom + width / 2,
        y: (node.y - camera.y) * camera.zoom + height / 2,
      });
      context.setTransform(dpr, 0, 0, dpr, 0, 0);
      context.clearRect(0, 0, width, height);
      context.fillStyle = "#07131f";
      context.fillRect(0, 0, width, height);
      context.fillStyle = "rgba(143, 163, 181, 0.13)";
      for (let x = 18; x < width; x += 28)
        for (let y = 18; y < height; y += 28) context.fillRect(x, y, 1, 1);

      for (const [index, edge] of edges.entries()) {
        const aNode = sim.get(edge.source);
        const bNode = sim.get(edge.target);
        if (!aNode || !bNode || time < Math.max(aNode.bornAt, bNode.bornAt))
          continue;
        const a = screen(aNode);
        const b = screen(bNode);
        const controlWorld = edgeControl(
          aNode,
          bNode,
          (index % 2 ? 1 : -1) * 24,
        );
        const control = {
          x: (controlWorld.x - camera.x) * camera.zoom + width / 2,
          y: (controlWorld.y - camera.y) * camera.zoom + height / 2,
        };
        const color =
          edge.state === "pending"
            ? colors.pending
            : edge.state === "rejected"
              ? colors.rejected
              : bNode.kind === "page"
                ? colors.page
                : bNode.kind === "domain"
                  ? colors.seed
                  : colors.contact;
        context.beginPath();
        context.moveTo(a.x, a.y);
        context.quadraticCurveTo(control.x, control.y, b.x, b.y);
        context.strokeStyle = rgba(
          color,
          edge.state === "rejected" ? 0.42 : 0.72,
        );
        context.lineWidth = edge.state === "verified" ? 1.5 : 1.25;
        context.setLineDash(
          edge.state === "pending"
            ? [7, 6]
            : edge.state === "rejected"
              ? [2, 7]
              : [],
        );
        context.stroke();
        context.setLineDash([]);
        if (!reducedMotionRef.current && edge.state !== "rejected") {
          for (const offset of [0, 0.5]) {
            const progress = (time * 0.00017 + index * 0.19 + offset) % 1;
            const packet = quadraticPoint(a, control, b, progress);
            const glow = context.createRadialGradient(
              packet.x,
              packet.y,
              0,
              packet.x,
              packet.y,
              8,
            );
            glow.addColorStop(0, rgba(color, 0.9));
            glow.addColorStop(1, rgba(color, 0));
            context.fillStyle = glow;
            context.beginPath();
            context.arc(packet.x, packet.y, 8, 0, Math.PI * 2);
            context.fill();
            context.fillStyle = color;
            context.beginPath();
            context.arc(packet.x, packet.y, 2.2, 0, Math.PI * 2);
            context.fill();
          }
        }
      }

      for (const node of values) {
        if (time < node.bornAt) continue;
        const point = screen(node);
        const baseRadius = nodeRadius(node) * camera.zoom;
        const age = Math.min(1, Math.max(0, (time - node.bornAt) / 430));
        const radius = baseRadius * (0.55 + age * 0.45);
        const color = nodeColor(node);
        const isSelected = selectedRef.current === node.id;
        const isHovered = hoveredRef.current === node.id;
        const pulse = reducedMotionRef.current ? 0 : Math.sin(time * 0.004) * 3;
        if (isSelected || node.id === "seed") {
          const glow = context.createRadialGradient(
            point.x,
            point.y,
            radius * 0.25,
            point.x,
            point.y,
            radius * 2.1 + pulse,
          );
          glow.addColorStop(0, rgba(color, 0.22));
          glow.addColorStop(1, rgba(color, 0));
          context.fillStyle = glow;
          context.beginPath();
          context.arc(point.x, point.y, radius * 2.1 + pulse, 0, Math.PI * 2);
          context.fill();
        }
        context.beginPath();
        context.arc(
          point.x,
          point.y,
          radius + (isSelected ? 8 : isHovered ? 5 : 3),
          0,
          Math.PI * 2,
        );
        context.strokeStyle = rgba(color, isSelected ? 0.85 : 0.32);
        context.lineWidth = isSelected ? 2 : 1;
        context.stroke();
        context.beginPath();
        context.arc(point.x, point.y, radius, 0, Math.PI * 2);
        context.fillStyle = "#0b1824";
        context.fill();
        context.strokeStyle = color;
        context.lineWidth = isSelected ? 3 : 2;
        context.setLineDash(node.state === "pending" ? [5, 4] : []);
        context.stroke();
        context.setLineDash([]);
        drawIcon(
          context,
          node.kind,
          point.x,
          point.y,
          Math.max(
            10,
            radius *
              (node.kind === "telegram" || node.kind === "whatsapp"
                ? 0.84
                : 0.42),
          ),
          color,
        );
        context.textAlign = "center";
        context.textBaseline = "middle";
        context.font = `700 ${Math.max(11, 13 * camera.zoom)}px "Geist Variable", sans-serif`;
        const labelWidth = context.measureText(node.label).width + 16;
        context.fillStyle = "rgba(5, 15, 24, 0.88)";
        context.beginPath();
        context.roundRect(
          point.x - labelWidth / 2,
          point.y + radius + 9,
          labelWidth,
          24,
          7,
        );
        context.fill();
        context.fillStyle = "#f5f7fa";
        context.fillText(node.label, point.x, point.y + radius + 21);
        if (camera.zoom > 0.63) {
          context.font = `500 ${Math.max(9, 10 * camera.zoom)}px "Geist Variable", sans-serif`;
          context.fillStyle = "#8fa3b5";
          context.fillText(
            localizedNode(node, language).detail,
            point.x,
            point.y + radius + 43,
          );
        }
      }

      if (!reducedMotionRef.current && values.length > 1) {
        const available = values.filter((node) => time >= node.bornAt);
        const targetIndex = Math.floor(time / 2100) % available.length;
        const target = available[targetIndex];
        if (target) {
          const destination = screen(target);
          const previous =
            available[(targetIndex - 1 + available.length) % available.length];
          const source = screen(previous ?? target);
          const phase = (time % 2100) / 2100;
          const eased =
            phase < 0.5
              ? 2 * phase * phase
              : 1 - Math.pow(-2 * phase + 2, 2) / 2;
          const cursorX =
            source.x +
            (destination.x - source.x) * eased +
            Math.sin(phase * Math.PI) * 28;
          const cursorY =
            source.y +
            (destination.y - source.y) * eased -
            Math.sin(phase * Math.PI) * 26;

          const scanGlow = context.createRadialGradient(
            destination.x,
            destination.y,
            0,
            destination.x,
            destination.y,
            56 + Math.sin(time * 0.008) * 8,
          );
          scanGlow.addColorStop(0, "rgba(237, 23, 100, .16)");
          scanGlow.addColorStop(1, "rgba(237, 23, 100, 0)");
          context.fillStyle = scanGlow;
          context.beginPath();
          context.arc(destination.x, destination.y, 62, 0, Math.PI * 2);
          context.fill();
          context.strokeStyle = "rgba(237, 23, 100, .55)";
          context.lineWidth = 1;
          context.setLineDash([4, 6]);
          context.beginPath();
          context.arc(
            destination.x,
            destination.y,
            43 + Math.sin(time * 0.006) * 4,
            0,
            Math.PI * 2,
          );
          context.stroke();
          context.setLineDash([]);

          context.save();
          context.translate(cursorX, cursorY);
          context.rotate(-0.14);
          context.shadowColor = "rgba(237, 23, 100, .7)";
          context.shadowBlur = 16;
          context.fillStyle = "#f5f7fa";
          context.strokeStyle = "#ed1764";
          context.lineWidth = 1.5;
          context.beginPath();
          context.moveTo(0, 0);
          context.lineTo(4, 19);
          context.lineTo(9, 13);
          context.lineTo(15, 22);
          context.lineTo(19, 19);
          context.lineTo(13, 11);
          context.lineTo(21, 9);
          context.closePath();
          context.fill();
          context.stroke();
          context.restore();

          const labelX = Math.min(width - 135, cursorX + 18);
          const labelY = Math.max(22, cursorY - 22);
          context.fillStyle = "rgba(7, 19, 31, .94)";
          context.strokeStyle = "rgba(237, 23, 100, .42)";
          context.beginPath();
          context.roundRect(labelX, labelY - 15, 112, 27, 8);
          context.fill();
          context.stroke();
          context.fillStyle = "#f5f7fa";
          context.textAlign = "left";
          context.textBaseline = "middle";
          context.font = '700 9px "Geist Variable", sans-serif';
          context.fillText(
            language === "id" ? "AGEN · MEMERIKSA" : "AGENT · INSPECTING",
            labelX + 9,
            labelY - 1,
          );
        }
      }

      const miniWidth = minimap.width / dpr;
      const miniHeight = minimap.height / dpr;
      mini.setTransform(dpr, 0, 0, dpr, 0, 0);
      mini.clearRect(0, 0, miniWidth, miniHeight);
      mini.fillStyle = "rgba(4, 13, 23, 0.94)";
      mini.fillRect(0, 0, miniWidth, miniHeight);
      const bounds = { minX: -390, maxX: 390, minY: -290, maxY: 290 };
      const miniPoint = (node: SimNode) => ({
        x: ((node.x - bounds.minX) / (bounds.maxX - bounds.minX)) * miniWidth,
        y: ((node.y - bounds.minY) / (bounds.maxY - bounds.minY)) * miniHeight,
      });
      mini.strokeStyle = "rgba(122,145,162,.24)";
      mini.lineWidth = 0.75;
      for (const edge of edges) {
        const a = sim.get(edge.source);
        const b = sim.get(edge.target);
        if (!a || !b) continue;
        const ap = miniPoint(a);
        const bp = miniPoint(b);
        mini.beginPath();
        mini.moveTo(ap.x, ap.y);
        mini.lineTo(bp.x, bp.y);
        mini.stroke();
      }
      for (const node of values) {
        const point = miniPoint(node);
        mini.fillStyle = nodeColor(node);
        mini.beginPath();
        mini.arc(
          point.x,
          point.y,
          node.id === "seed" ? 3.8 : 2.5,
          0,
          Math.PI * 2,
        );
        mini.fill();
      }
      const worldWidth = width / camera.zoom;
      const worldHeight = height / camera.zoom;
      mini.strokeStyle = "rgba(237, 70, 127, .76)";
      mini.lineWidth = 1;
      mini.strokeRect(
        ((camera.x - worldWidth / 2 - bounds.minX) /
          (bounds.maxX - bounds.minX)) *
          miniWidth,
        ((camera.y - worldHeight / 2 - bounds.minY) /
          (bounds.maxY - bounds.minY)) *
          miniHeight,
        (worldWidth / (bounds.maxX - bounds.minX)) * miniWidth,
        (worldHeight / (bounds.maxY - bounds.minY)) * miniHeight,
      );
      frame = window.requestAnimationFrame(paint);
    };
    frame = window.requestAnimationFrame(paint);
    return () => window.cancelAnimationFrame(frame);
  }, [edges, language]);

  const screenNodeAt = (clientX: number, clientY: number) => {
    const canvas = canvasRef.current;
    if (!canvas) return undefined;
    const bounds = canvas.getBoundingClientRect();
    const x = clientX - bounds.left;
    const y = clientY - bounds.top;
    const camera = cameraRef.current;
    const size = sizeRef.current;
    return [...simulationRef.current.values()].reverse().find((node) => {
      const sx = (node.x - camera.x) * camera.zoom + size.width / 2;
      const sy = (node.y - camera.y) * camera.zoom + size.height / 2;
      return (
        Math.hypot(sx - x, sy - y) <=
        Math.max(18, nodeRadius(node) * camera.zoom + 9)
      );
    });
  };

  const onPointerDown = (event: PointerEvent<HTMLCanvasElement>) => {
    event.currentTarget.setPointerCapture(event.pointerId);
    const node = screenNodeAt(event.clientX, event.clientY);
    if (node) node.pinned = true;
    pointerRef.current = {
      id: event.pointerId,
      startX: event.clientX,
      startY: event.clientY,
      cameraX: cameraRef.current.targetX,
      cameraY: cameraRef.current.targetY,
      dragId: node?.id,
      moved: false,
    };
  };

  const onPointerMove = (event: PointerEvent<HTMLCanvasElement>) => {
    const pointer = pointerRef.current;
    const canvas = canvasRef.current;
    if (!canvas) return;
    if (pointer) {
      const dx = event.clientX - pointer.startX;
      const dy = event.clientY - pointer.startY;
      pointer.moved ||= Math.hypot(dx, dy) > 3;
      if (pointer.dragId) {
        const node = simulationRef.current.get(pointer.dragId);
        if (node) {
          node.x += event.movementX / cameraRef.current.zoom;
          node.y += event.movementY / cameraRef.current.zoom;
          node.vx = event.movementX / cameraRef.current.zoom;
          node.vy = event.movementY / cameraRef.current.zoom;
        }
      } else {
        cameraRef.current.targetX =
          pointer.cameraX - dx / cameraRef.current.zoom;
        cameraRef.current.targetY =
          pointer.cameraY - dy / cameraRef.current.zoom;
      }
      return;
    }
    const node = screenNodeAt(event.clientX, event.clientY);
    hoveredRef.current = node?.id ?? null;
    canvas.style.cursor = node ? "pointer" : "grab";
    if (node) {
      const bounds = canvas.getBoundingClientRect();
      setHovered({
        node,
        x: event.clientX - bounds.left,
        y: event.clientY - bounds.top,
      });
    } else setHovered(null);
  };

  const onPointerUp = (event: PointerEvent<HTMLCanvasElement>) => {
    const pointer = pointerRef.current;
    if (pointer?.dragId) {
      const node = simulationRef.current.get(pointer.dragId);
      if (node) {
        releaseWithMomentum(node);
        if (!pointer.moved) selectNode(node);
      }
    }
    pointerRef.current = null;
    event.currentTarget.releasePointerCapture(event.pointerId);
  };

  const onWheel = (event: WheelEvent<HTMLCanvasElement>) => {
    event.preventDefault();
    const camera = cameraRef.current;
    camera.targetZoom = Math.max(
      0.48,
      Math.min(1.8, camera.targetZoom * (event.deltaY > 0 ? 0.88 : 1.13)),
    );
  };

  const zoom = (factor: number) => {
    const camera = cameraRef.current;
    camera.targetZoom = Math.max(
      0.48,
      Math.min(1.8, camera.targetZoom * factor),
    );
  };

  return (
    <section
      className={`canvas-graph ${compact ? "canvas-graph--compact" : ""}`}
      aria-label={
        language === "id"
          ? "Graph bukti interaktif"
          : "Interactive evidence graph"
      }
    >
      <div className="canvas-graph__stage" ref={containerRef}>
        <canvas
          ref={canvasRef}
          role="img"
          aria-label={
            language === "id"
              ? "Graph interaktif berisi halaman tersimpan, observasi kontak publik, dan kandidat tertunda"
              : "Interactive graph of captured pages, public contact observations, and pending candidates"
          }
          tabIndex={0}
          onPointerDown={onPointerDown}
          onPointerMove={onPointerMove}
          onPointerUp={onPointerUp}
          onPointerCancel={onPointerUp}
          onPointerLeave={() => {
            if (!pointerRef.current) {
              hoveredRef.current = null;
              setHovered(null);
            }
          }}
          onWheel={onWheel}
        />
        <div
          className="canvas-graph__controls"
          aria-label="Graph view controls"
        >
          <button
            type="button"
            onClick={() => zoom(1.22)}
            aria-label="Zoom in"
            title="Zoom in"
          >
            <MagnifyingGlassPlusIcon />
          </button>
          <button
            type="button"
            onClick={() => zoom(0.82)}
            aria-label="Zoom out"
            title="Zoom out"
          >
            <MagnifyingGlassMinusIcon />
          </button>
          <button
            type="button"
            onClick={fitView}
            aria-label="Fit graph to view"
            title="Fit view"
          >
            <CornersOutIcon />
          </button>
        </div>
        <canvas
          ref={minimapRef}
          className="canvas-graph__minimap"
          aria-hidden="true"
        />
        <GraphLegend language={language} />
        {hovered && (
          <div
            className="canvas-graph__tooltip"
            style={{ left: hovered.x, top: hovered.y }}
          >
            <strong>{hovered.node.label}</strong>
            <span>{localizedNode(hovered.node, language).detail}</span>
            <small>
              {language === "id"
                ? "Klik untuk periksa · tarik untuk gerakkan"
                : "Click to inspect · drag to move"}
            </small>
          </div>
        )}
        <div className="canvas-graph__activity" aria-hidden="true">
          <i />
          <span>
            {language === "id"
              ? "Agen menelusuri bukti publik"
              : "Agent exploring public evidence"}
          </span>
        </div>
        <div className="canvas-graph__agent-status" aria-hidden="true">
          <span>{language === "id" ? "DIBANTU MODEL" : "MODEL-ASSISTED"}</span>
          <strong>
            {language === "id"
              ? "Aksi browser aman dipilih"
              : "Safe browser action selected"}
          </strong>
          <small>
            {language === "id"
              ? "Konteks ternormalisasi · referensi dari server saja"
              : "Normalized context · server-issued references only"}
          </small>
        </div>
      </div>
      {!compact && active && (
        <aside className="graph-inspector" aria-live="polite">
          <span className="graph-inspector__state" data-state={active.state}>
            {active.state}
          </span>
          <p className="graph-inspector__kind">
            {language === "id" ? "Dipilih" : "Selected"} {active.kind}
          </p>
          <h3>{active.label}</h3>
          <p>{localizedNode(active, language).detail}</p>
          <dl>
            <div>
              <dt>{language === "id" ? "Sumber" : "Source"}</dt>
              <dd>{localizedNode(active, language).source}</dd>
            </div>
            <div>
              <dt>{language === "id" ? "Pertama terlihat" : "First seen"}</dt>
              <dd>12 Aug 2026 · 07:03 WIB</dd>
            </div>
            <div>
              <dt>{language === "id" ? "Tinjauan" : "Review"}</dt>
              <dd>
                {active.state === "pending"
                  ? language === "id"
                    ? "Perlu tinjauan manusia"
                    : "Human review required"
                  : active.state === "rejected"
                    ? language === "id"
                      ? "Ditolak peninjau"
                      : "Rejected by reviewer"
                    : language === "id"
                      ? "Bukti terverifikasi"
                      : "Evidence verified"}
              </dd>
            </div>
          </dl>
          <p className="graph-inspector__note">
            {language === "id"
              ? "Hanya observasi. Tampilan ini tidak menetapkan kepemilikan atau identitas operator."
              : "Observation only. This view does not establish ownership or operator identity."}
          </p>
        </aside>
      )}
      <details className="graph-fallback">
        <summary>
          {language === "id"
            ? "Tabel graph aksesibel"
            : "Accessible graph table"}
        </summary>
        <table>
          <thead>
            <tr>
              <th>{language === "id" ? "Entitas" : "Entity"}</th>
              <th>{language === "id" ? "Jenis" : "Type"}</th>
              <th>Status</th>
              <th>{language === "id" ? "Sumber" : "Source"}</th>
            </tr>
          </thead>
          <tbody>
            {nodes.map((node) => (
              <tr key={node.id}>
                <td>{node.label}</td>
                <td>{node.kind}</td>
                <td>{node.state}</td>
                <td>{localizedNode(node, language).source}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </details>
    </section>
  );
}
