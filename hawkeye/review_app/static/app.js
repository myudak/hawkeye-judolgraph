"use strict";

const refs = {
  scanForm: document.getElementById("scan-form"),
  seedInput: document.getElementById("seed-url"),
  scanButton: document.getElementById("scan-button"),
  workspaceSelector: document.getElementById("workspace-selector"),
  capabilityState: document.getElementById("capability-state"),
  intelContent: document.getElementById("intel-content"),
  graphCanvas: document.getElementById("graph-canvas"),
  graphEmpty: document.getElementById("graph-empty"),
  graphTooltip: document.getElementById("graph-tooltip"),
  graphA11y: document.getElementById("graph-a11y"),
  graphCount: document.getElementById("graph-count"),
  graphModeLabel: document.getElementById("graph-mode-label"),
  graphSearch: document.getElementById("graph-search"),
  inspectorContent: document.getElementById("inspector-content"),
  timelineTrack: document.getElementById("timeline-track"),
  replayButton: document.getElementById("replay-button"),
  pauseButton: document.getElementById("pause-button"),
  timelineSpeed: document.getElementById("timeline-speed"),
  zoomOut: document.getElementById("zoom-out"),
  zoomIn: document.getElementById("zoom-in"),
  fitGraph: document.getElementById("fit-graph"),
  statusLine: document.getElementById("status-line"),
  toastRegion: document.getElementById("toast-region"),
};

const evidenceSemantics = {
  candidate: "Relationship: not determined",
  comparison: "Evidence-similarity score",
  accessibility: "accessible relationship table",
  current: "aria-current",
};

const ctx = refs.graphCanvas.getContext("2d", { alpha: true });
const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
const colors = {
  case: "#70b7ff",
  domain: "#58e9b0",
  page: "#68b4ff",
  seed_page: "#68b4ff",
  collected_page: "#5cecad",
  screenshot: "#ef80c2",
  document: "#aa91ff",
  readiness: "#63dce9",
  observation: "#ffbd68",
  public_contact: "#ffbd68",
  external_destination: "#f09a63",
  redirect_target: "#f09a63",
  candidate: "#ffb75a",
  candidate_domain: "#ffb75a",
  claimed_brand: "#d894ff",
  default: "#aab5c1",
};

const view = {
  cases: [],
  runs: [],
  currentKind: null,
  currentDetails: null,
  nodes: [],
  edges: [],
  nodeById: new Map(),
  timeline: [],
  selectedId: null,
  hoverId: null,
  searchIds: new Set(),
  query: "",
  playbackCutoff: Number.POSITIVE_INFINITY,
  replayTimer: null,
  replayPaused: false,
  replayPosition: 0,
  camera: { x: 0, y: 0, zoom: 0.82, targetX: 0, targetY: 0, targetZoom: 0.82 },
  width: 0,
  height: 0,
  dpr: 1,
  pointer: null,
  dragNode: null,
  frameTime: performance.now(),
};

function el(tag, className, text) {
  const element = document.createElement(tag);
  if (className) element.className = className;
  if (text !== undefined && text !== null) element.textContent = String(text);
  return element;
}

function valueOr(value, fallback = "Not recorded") {
  return value === undefined || value === null || value === "" ? fallback : String(value);
}

function titleCase(value) {
  return valueOr(value).replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function shortText(value, length = 34) {
  const text = valueOr(value, "Untitled");
  return text.length <= length ? text : `${text.slice(0, length - 1)}…`;
}

function formatTime(value) {
  if (!value) return "time not recorded";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return String(value);
  return new Intl.DateTimeFormat("en-GB", {
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  }).format(parsed);
}

function hostnameFrom(value) {
  try {
    return new URL(value).hostname.replace(/^www\./, "");
  } catch {
    return valueOr(value, "saved evidence").split("/")[0];
  }
}

function setStatus(message) {
  refs.statusLine.textContent = message;
}

function toast(message, kind = "") {
  const item = el("div", `toast ${kind}`.trim(), message);
  refs.toastRegion.append(item);
  window.setTimeout(() => item.remove(), 4200);
}

async function requestJson(path, options = {}) {
  const response = await fetch(path, {
    credentials: "same-origin",
    cache: "no-store",
    ...options,
  });
  if (!response.ok) {
    let detail = `Request failed (${response.status})`;
    try {
      const payload = await response.json();
      detail = payload.error || payload.detail || detail;
    } catch {
      // The status code remains the safe failure detail.
    }
    throw new Error(detail);
  }
  return response.json();
}

function postJson(path, payload) {
  return requestJson(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

function caseArtifactUrl(caseId, evidenceId) {
  return `/api/cases/${encodeURIComponent(caseId)}/artifacts/${encodeURIComponent(evidenceId)}`;
}

function runArtifactUrl(workspaceId, name) {
  return `/api/mvp/runs/${encodeURIComponent(workspaceId)}/artifacts/${encodeURIComponent(name)}`;
}

function hash(value) {
  let result = 2166136261;
  for (const character of String(value)) {
    result ^= character.charCodeAt(0);
    result = Math.imul(result, 16777619);
  }
  return result >>> 0;
}

function seededUnit(value) {
  return (hash(value) % 10000) / 10000;
}

function nodeKind(rawType) {
  const type = String(rawType || "default").toLowerCase();
  if (type.includes("screenshot")) return "screenshot";
  if (type.includes("readiness")) return "readiness";
  if (type.includes("html") || type.includes("text") || type.includes("network")) return "document";
  if (type.includes("candidate")) return "candidate_domain";
  return type;
}

function clusterFor(kind) {
  if (["case", "domain", "page", "seed_page", "collected_page"].includes(kind)) return "Captured pages";
  if (["screenshot", "document", "readiness"].includes(kind)) return "Evidence artifacts";
  if (["observation", "public_contact", "claimed_brand"].includes(kind)) return "Observed signals";
  if (["candidate", "candidate_domain", "external_destination", "redirect_target"].includes(kind)) return "Pending leads";
  return "Evidence graph";
}

function nodeCode(kind) {
  const codes = {
    case: "CASE",
    domain: "DOM",
    page: "PG",
    seed_page: "A",
    collected_page: "B",
    screenshot: "IMG",
    document: "DOC",
    readiness: "RDY",
    observation: "OBS",
    public_contact: "TEL",
    external_destination: "EXT",
    redirect_target: "301",
    candidate: "LEAD",
    candidate_domain: "LEAD",
    claimed_brand: "BR",
  };
  return codes[kind] || "EV";
}

function radiusFor(kind, primary) {
  if (primary) return 19;
  if (["case", "domain", "page", "seed_page", "collected_page"].includes(kind)) return 14;
  return 11;
}

function normalizeNode(raw, index, extras = {}) {
  const kind = nodeKind(raw.kind || raw.type);
  return {
    id: String(raw.id),
    kind,
    label: valueOr(raw.label, raw.id),
    status: raw.status || extras.status || "observed",
    attributes: raw.attributes || extras.attributes || {},
    cluster: extras.cluster || clusterFor(kind),
    sequence: Number(extras.sequence || raw.sequence || index + 1),
    primary: Boolean(extras.primary),
    x: 0,
    y: 0,
    vx: 0,
    vy: 0,
    tx: 0,
    ty: 0,
    pinned: false,
    birth: performance.now() + index * 38,
    radius: radiusFor(kind, Boolean(extras.primary)),
  };
}

function normalizeEdge(raw, index, extras = {}) {
  const source = typeof raw.source === "object" ? raw.source.id : raw.source;
  const target = typeof raw.target === "object" ? raw.target.id : raw.target;
  return {
    id: String(raw.id || `edge-${index}`),
    source: String(source),
    target: String(target),
    relation: valueOr(raw.relation || raw.type, "recorded relation"),
    appearance: raw.appearance || extras.appearance || "solid",
    sequence: Number(extras.sequence || raw.sequence || index + 2),
    evidence: raw.evidence || null,
    birth: performance.now() + 160 + index * 44,
    seed: seededUnit(raw.id || `${source}-${target}`),
  };
}

function addUniqueNode(nodes, node) {
  if (!nodes.some((item) => item.id === node.id)) nodes.push(node);
}

function addUniqueEdge(edges, edge) {
  if (!edges.some((item) => item.id === edge.id)) edges.push(edge);
}

function buildCaseProjection(details) {
  const nodes = [];
  const edges = [];
  const timeline = [];
  const sourceNodes = details.graph?.nodes || [];
  const primarySource = sourceNodes.find((item) => item.type === "page") || sourceNodes.find((item) => item.type === "domain") || sourceNodes[0];
  sourceNodes.forEach((raw, index) => {
    addUniqueNode(nodes, normalizeNode(raw, index, {
      primary: raw.id === primarySource?.id,
      sequence: 1,
      attributes: { source: "persisted graph node", raw },
    }));
  });
  (details.graph?.edges || []).forEach((raw, index) => {
    addUniqueEdge(edges, normalizeEdge(raw, index, {
      sequence: 2 + index,
      appearance: raw.relationship_status === "observed_evidence" ? "solid_emphasized" : "solid",
    }));
  });

  if (!nodes.length) {
    const caseNode = normalizeNode({ id: `case:${details.case_id}`, type: "case", label: details.case_id }, 0, { primary: true, sequence: 1 });
    addUniqueNode(nodes, caseNode);
    (details.pages || []).forEach((page, index) => {
      const pageNode = normalizeNode({ id: `page:${page.id}`, type: "page", label: page.final_url_display }, index + 1, { sequence: index + 2, attributes: { page } });
      addUniqueNode(nodes, pageNode);
      addUniqueEdge(edges, normalizeEdge({ id: `case-page:${page.id}`, source: caseNode.id, target: pageNode.id, relation: "contains captured page" }, edges.length, { sequence: index + 2 }));
    });
  }

  const pageNodes = new Map();
  nodes.filter((item) => item.kind === "page").forEach((item) => {
    const pageId = item.id.startsWith("page:") ? item.id.slice(5) : item.id;
    pageNodes.set(pageId, item.id);
  });
  let sequence = Math.max(3, edges.length + 2);
  (details.evidence || []).forEach((record, index) => {
    sequence += 1;
    const evidenceNode = normalizeNode({
      id: `evidence:${record.id}`,
      type: record.type,
      label: titleCase(record.type),
    }, nodes.length, {
      sequence,
      attributes: { evidence: record },
    });
    addUniqueNode(nodes, evidenceNode);
    const sourceId = pageNodes.get(record.page_id) || primarySource?.id || nodes[0]?.id;
    if (sourceId) {
      addUniqueEdge(edges, normalizeEdge({
        id: `captured:${record.id}`,
        source: sourceId,
        target: evidenceNode.id,
        relation: "captured as",
      }, edges.length, { sequence }));
    }
    timeline.push({
      sequence,
      label: titleCase(record.type),
      detail: formatTime(record.collected_at),
      occurredAt: record.collected_at,
      targetId: evidenceNode.id,
    });
  });

  (details.observations || []).forEach((observation) => {
    sequence += 1;
    const observationNode = normalizeNode({
      id: `observation:${observation.id}`,
      type: observation.type || "observation",
      label: observation.display_value,
    }, nodes.length, { sequence, attributes: { observation } });
    observationNode.kind = observationNode.kind === "default" ? "observation" : observationNode.kind;
    observationNode.cluster = "Observed signals";
    addUniqueNode(nodes, observationNode);
    const sourceId = `evidence:${observation.source_artifact_id}`;
    if (nodes.some((item) => item.id === sourceId)) {
      addUniqueEdge(edges, normalizeEdge({ id: `supports:${observation.id}`, source: sourceId, target: observationNode.id, relation: "supports observation" }, edges.length, { sequence }));
    }
    timeline.push({ sequence, label: titleCase(observation.type), detail: "Semantic observation recorded", targetId: observationNode.id });
  });

  (details.candidates || []).forEach((candidate) => {
    sequence += 1;
    const candidateId = `candidate:${candidate.candidate_id}`;
    addUniqueNode(nodes, normalizeNode({ id: candidateId, type: "candidate_domain", label: candidate.hostname }, nodes.length, {
      sequence,
      status: "lead",
      attributes: { candidate },
    }));
    const reason = candidate.reasons?.[0];
    const sourceEvidenceId = reason?.evidence_refs?.[0]?.evidence_id;
    const sourceId = sourceEvidenceId && nodes.some((item) => item.id === `evidence:${sourceEvidenceId}`)
      ? `evidence:${sourceEvidenceId}`
      : primarySource?.id || nodes[0]?.id;
    if (sourceId) addUniqueEdge(edges, normalizeEdge({ id: `lead:${candidate.candidate_id}`, source: sourceId, target: candidateId, relation: "pending candidate lead" }, edges.length, { sequence, appearance: "dashed" }));
    timeline.push({ sequence, label: "Candidate recorded", detail: evidenceSemantics.candidate, targetId: candidateId });
  });

  timeline.unshift({ sequence: 1, label: "Capture started", detail: formatTime(details.started_at), occurredAt: details.started_at, targetId: primarySource?.id || nodes[0]?.id });
  sequence += 1;
  timeline.push({
    sequence,
    label: details.capture_adequacy === "adequate" ? "Capture adequate" : "Capture limited",
    detail: formatTime(details.completed_at),
    occurredAt: details.completed_at,
    targetId: primarySource?.id || nodes[0]?.id,
  });
  return { nodes, edges, timeline, mode: "Saved public observation" };
}

function buildRunProjection(details) {
  const eventSequence = new Map((details.events || []).map((event) => [event.event_id, event.sequence]));
  const animationSequence = new Map();
  (details.graph?.animations || []).forEach((animation) => {
    const existing = animationSequence.get(animation.target_id) || Number.POSITIVE_INFINITY;
    animationSequence.set(animation.target_id, Math.min(existing, animation.sequence));
  });
  const nodes = (details.graph?.nodes || []).map((raw, index) => normalizeNode(raw, index, {
    primary: raw.kind === "seed_page",
    sequence: animationSequence.get(raw.id) || index + 1,
    attributes: raw.attributes || {},
  }));
  const edges = (details.graph?.edges || []).map((raw, index) => normalizeEdge(raw, index, {
    sequence: Math.min(...(raw.supporting_event_ids || []).map((id) => eventSequence.get(id) || 999), index + 2),
  }));
  const timeline = (details.events || []).map((event) => ({
    sequence: event.sequence,
    label: titleCase(event.kind.replaceAll(".", " ")),
    detail: formatTime(event.occurred_at),
    occurredAt: event.occurred_at,
    targetId: (details.graph?.animations || []).find((item) => item.sequence === event.sequence)?.target_id || null,
    event,
  }));
  return { nodes, edges, timeline, mode: "Event-driven investigation" };
}

function applyLayoutTargets() {
  const buckets = new Map();
  view.nodes.forEach((item) => {
    if (!buckets.has(item.cluster)) buckets.set(item.cluster, []);
    buckets.get(item.cluster).push(item);
  });
  const centers = {
    "Captured pages": { x: -70, y: 0 },
    "Evidence artifacts": { x: -250, y: 80 },
    "Observed signals": { x: 210, y: -100 },
    "Pending leads": { x: 285, y: 115 },
    "Evidence graph": { x: 0, y: 0 },
  };
  for (const [cluster, items] of buckets) {
    const center = centers[cluster] || centers["Evidence graph"];
    items.forEach((item, index) => {
      if (item.primary) {
        item.tx = 0;
        item.ty = 0;
      } else {
        const angle = (index / Math.max(1, items.length)) * Math.PI * 2 + seededUnit(item.id) * 0.8;
        const ring = 58 + Math.min(180, items.length * 17) + (index % 2) * 34;
        item.tx = center.x + Math.cos(angle) * ring;
        item.ty = center.y + Math.sin(angle) * ring * 0.72;
      }
      if (item.x === 0 && item.y === 0 && !item.primary) {
        item.x = item.tx * 0.42 + (seededUnit(`${item.id}:x`) - 0.5) * 100;
        item.y = item.ty * 0.42 + (seededUnit(`${item.id}:y`) - 0.5) * 100;
      }
    });
  }
}

function setGraph(projection) {
  stopReplay();
  view.nodes = projection.nodes;
  view.edges = projection.edges.filter((edge) => projection.nodes.some((node) => node.id === edge.source) && projection.nodes.some((node) => node.id === edge.target));
  view.nodeById = new Map(view.nodes.map((item) => [item.id, item]));
  view.timeline = projection.timeline.sort((a, b) => a.sequence - b.sequence);
  view.playbackCutoff = Number.POSITIVE_INFINITY;
  view.selectedId = view.nodes.find((item) => item.primary)?.id || view.nodes[0]?.id || null;
  view.hoverId = null;
  view.searchIds.clear();
  applyLayoutTargets();
  refs.graphModeLabel.textContent = projection.mode;
  refs.graphCount.textContent = `${view.nodes.length} nodes · ${view.edges.length} links`;
  refs.graphEmpty.hidden = view.nodes.length > 0;
  renderTimeline();
  renderAccessibleGraph();
  window.setTimeout(fitGraph, 80);
}

function renderAccessibleGraph() {
  const title = el("h2", "", evidenceSemantics.accessibility);
  const description = el("p", "", `${view.nodes.length} nodes and ${view.edges.length} recorded links.`);
  const list = el("ul");
  view.edges.forEach((edge) => {
    const source = view.nodeById.get(edge.source);
    const target = view.nodeById.get(edge.target);
    list.append(el("li", "", `${source?.label || edge.source} — ${edge.relation} — ${target?.label || edge.target}`));
  });
  refs.graphA11y.replaceChildren(title, description, list);
}

function resizeCanvas() {
  const rect = refs.graphCanvas.getBoundingClientRect();
  view.dpr = Math.min(1.75, window.devicePixelRatio || 1);
  view.width = Math.max(320, rect.width);
  view.height = Math.max(360, rect.height);
  refs.graphCanvas.width = Math.floor(view.width * view.dpr);
  refs.graphCanvas.height = Math.floor(view.height * view.dpr);
  ctx.setTransform(view.dpr, 0, 0, view.dpr, 0, 0);
}

function worldToScreen(item, time = 0) {
  const float = reduceMotion ? 0 : Math.sin(time * 0.0012 + seededUnit(item.id) * Math.PI * 2) * 2.4;
  return {
    x: (item.x - view.camera.x) * view.camera.zoom + view.width / 2,
    y: (item.y + float - view.camera.y) * view.camera.zoom + view.height / 2,
  };
}

function screenToWorld(x, y) {
  return {
    x: (x - view.width / 2) / view.camera.zoom + view.camera.x,
    y: (y - view.height / 2) / view.camera.zoom + view.camera.y,
  };
}

function isVisible(item) {
  return item.sequence <= view.playbackCutoff;
}

function physicsStep(delta) {
  const step = Math.min(2, delta / 16.67);
  for (const item of view.nodes) {
    if (item.pinned) continue;
    item.vx += (item.tx - item.x) * 0.0018 * step;
    item.vy += (item.ty - item.y) * 0.0018 * step;
  }
  for (let left = 0; left < view.nodes.length; left += 1) {
    for (let right = left + 1; right < view.nodes.length; right += 1) {
      const a = view.nodes[left];
      const b = view.nodes[right];
      let dx = b.x - a.x;
      let dy = b.y - a.y;
      const distanceSquared = Math.max(180, dx * dx + dy * dy);
      const distance = Math.sqrt(distanceSquared);
      dx /= distance;
      dy /= distance;
      const force = Math.min(0.52, 720 / distanceSquared) * step;
      if (!a.pinned) { a.vx -= dx * force; a.vy -= dy * force; }
      if (!b.pinned) { b.vx += dx * force; b.vy += dy * force; }
    }
  }
  view.edges.forEach((edge) => {
    const a = view.nodeById.get(edge.source);
    const b = view.nodeById.get(edge.target);
    if (!a || !b) return;
    const dx = b.x - a.x;
    const dy = b.y - a.y;
    const distance = Math.max(1, Math.hypot(dx, dy));
    const desired = 118;
    const pull = (distance - desired) * 0.00035 * step;
    if (!a.pinned) { a.vx += dx * pull; a.vy += dy * pull; }
    if (!b.pinned) { b.vx -= dx * pull; b.vy -= dy * pull; }
  });
  view.nodes.forEach((item) => {
    if (item.pinned) return;
    item.vx *= 0.91;
    item.vy *= 0.91;
    item.x += item.vx * step;
    item.y += item.vy * step;
  });
}

function roundedLabel(text, x, y, selected) {
  ctx.font = "600 10px 'Cascadia Mono', Consolas, monospace";
  const label = shortText(text, 27);
  const width = Math.min(190, ctx.measureText(label).width + 16);
  ctx.fillStyle = selected ? "rgba(18,31,39,.94)" : "rgba(5,9,13,.82)";
  ctx.strokeStyle = selected ? "rgba(95,226,239,.68)" : "rgba(156,177,194,.15)";
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.roundRect(x - width / 2, y, width, 22, 7);
  ctx.fill();
  ctx.stroke();
  ctx.fillStyle = selected ? "#f5fbff" : "#a4adb8";
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.fillText(label, x, y + 11, width - 10);
}

function drawClusters(time) {
  const groups = new Map();
  view.nodes.filter(isVisible).forEach((item) => {
    if (!groups.has(item.cluster)) groups.set(item.cluster, []);
    groups.get(item.cluster).push(item);
  });
  for (const [name, items] of groups) {
    if (items.length < 2) continue;
    const points = items.map((item) => worldToScreen(item, time));
    const cx = points.reduce((sum, point) => sum + point.x, 0) / points.length;
    const cy = points.reduce((sum, point) => sum + point.y, 0) / points.length;
    const rx = Math.max(70, ...points.map((point) => Math.abs(point.x - cx) + 40));
    const ry = Math.max(56, ...points.map((point) => Math.abs(point.y - cy) + 38));
    ctx.save();
    ctx.strokeStyle = name === "Pending leads" ? "rgba(255,183,90,.16)" : "rgba(92,183,238,.13)";
    ctx.fillStyle = name === "Pending leads" ? "rgba(255,183,90,.012)" : "rgba(71,148,207,.012)";
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.ellipse(cx, cy, rx, ry, 0, 0, Math.PI * 2);
    ctx.fill();
    ctx.stroke();
    ctx.fillStyle = "rgba(128,144,158,.58)";
    ctx.font = "600 9px 'Cascadia Mono', Consolas, monospace";
    ctx.textAlign = "left";
    ctx.fillText(name.toUpperCase(), cx - rx + 14, cy - ry + 20);
    ctx.restore();
  }
}

function curvePoints(edge, time) {
  const source = view.nodeById.get(edge.source);
  const target = view.nodeById.get(edge.target);
  if (!source || !target) return null;
  const a = worldToScreen(source, time);
  const b = worldToScreen(target, time);
  const dx = b.x - a.x;
  const dy = b.y - a.y;
  const length = Math.max(1, Math.hypot(dx, dy));
  const bend = (edge.seed - 0.5) * Math.min(72, length * 0.18);
  return { a, b, c: { x: (a.x + b.x) / 2 - (dy / length) * bend, y: (a.y + b.y) / 2 + (dx / length) * bend } };
}

function quadraticPoint(points, progress) {
  const inverse = 1 - progress;
  return {
    x: inverse * inverse * points.a.x + 2 * inverse * progress * points.c.x + progress * progress * points.b.x,
    y: inverse * inverse * points.a.y + 2 * inverse * progress * points.c.y + progress * progress * points.b.y,
  };
}

function drawEdges(time) {
  view.edges.filter(isVisible).forEach((edge) => {
    const points = curvePoints(edge, time);
    if (!points) return;
    const age = reduceMotion ? 1 : Math.min(1, Math.max(0, (time - edge.birth) / 650));
    const selected = edge.source === view.selectedId || edge.target === view.selectedId;
    const searchDimmed = view.query && !view.searchIds.has(edge.source) && !view.searchIds.has(edge.target);
    ctx.save();
    ctx.globalAlpha = (searchDimmed ? 0.08 : selected ? 0.96 : 0.48) * age;
    ctx.strokeStyle = edge.appearance === "solid_emphasized" ? "#57edae" : edge.appearance === "dashed" ? "#ffb75a" : "#6ab9f4";
    ctx.lineWidth = edge.appearance === "solid_emphasized" ? 2.6 : selected ? 1.8 : 1.15;
    if (edge.appearance === "dashed") ctx.setLineDash([7, 6]);
    ctx.shadowColor = ctx.strokeStyle;
    ctx.shadowBlur = selected || edge.appearance === "solid_emphasized" ? 8 : 0;
    const end = quadraticPoint(points, age);
    ctx.beginPath();
    ctx.moveTo(points.a.x, points.a.y);
    ctx.quadraticCurveTo(points.c.x, points.c.y, end.x, end.y);
    ctx.stroke();
    ctx.setLineDash([]);
    if (!reduceMotion && age === 1 && !searchDimmed) {
      const particle = quadraticPoint(points, (time * 0.00012 + edge.seed) % 1);
      ctx.globalAlpha = selected ? 1 : 0.72;
      ctx.fillStyle = ctx.strokeStyle;
      ctx.shadowBlur = 8;
      ctx.beginPath();
      ctx.arc(particle.x, particle.y, selected ? 2.4 : 1.7, 0, Math.PI * 2);
      ctx.fill();
    }
    ctx.restore();
  });
}

function drawNodes(time) {
  view.nodes.filter(isVisible).forEach((item) => {
    const point = worldToScreen(item, time);
    const age = reduceMotion ? 1 : Math.min(1, Math.max(0, (time - item.birth) / 420));
    const selected = item.id === view.selectedId;
    const hovered = item.id === view.hoverId;
    const searchDimmed = view.query && !view.searchIds.has(item.id);
    const color = colors[item.kind] || colors.default;
    const radius = item.radius * view.camera.zoom + 3;
    const pulse = reduceMotion ? 0 : Math.sin(time * 0.003 + seededUnit(item.id) * 6) * 2;
    ctx.save();
    ctx.globalAlpha = (searchDimmed ? 0.13 : 1) * age;
    ctx.translate(point.x, point.y);
    ctx.scale(0.45 + age * 0.55, 0.45 + age * 0.55);
    ctx.shadowColor = color;
    ctx.shadowBlur = selected ? 22 : hovered ? 15 : 8;
    ctx.fillStyle = `${color}16`;
    ctx.strokeStyle = selected ? "#ffffff" : color;
    ctx.lineWidth = selected ? 2.1 : item.status === "lead" ? 1.5 : 1.1;
    if (item.status === "lead") ctx.setLineDash([4, 3]);
    ctx.beginPath();
    ctx.arc(0, 0, radius + 6 + pulse * 0.25, 0, Math.PI * 2);
    ctx.fill();
    ctx.stroke();
    ctx.setLineDash([]);
    ctx.fillStyle = "#0b141c";
    ctx.strokeStyle = `${color}aa`;
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.arc(0, 0, radius, 0, Math.PI * 2);
    ctx.fill();
    ctx.stroke();
    ctx.shadowBlur = 10;
    ctx.fillStyle = color;
    ctx.beginPath();
    ctx.arc(radius * 0.45, -radius * 0.45, Math.max(2.2, radius * 0.18), 0, Math.PI * 2);
    ctx.fill();
    ctx.shadowBlur = 0;
    ctx.fillStyle = "#f4f8fb";
    ctx.font = `700 ${Math.max(7, Math.min(10, radius * 0.58))}px 'Cascadia Mono', Consolas, monospace`;
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillText(nodeCode(item.kind), 0, 0);
    ctx.restore();
    if (!searchDimmed && (selected || hovered || item.primary || view.camera.zoom > 0.74)) roundedLabel(item.label, point.x, point.y + radius + 10, selected);
  });
}

function drawFrame(time) {
  const delta = Math.min(40, time - view.frameTime);
  view.frameTime = time;
  physicsStep(delta);
  view.camera.x += (view.camera.targetX - view.camera.x) * 0.09;
  view.camera.y += (view.camera.targetY - view.camera.y) * 0.09;
  view.camera.zoom += (view.camera.targetZoom - view.camera.zoom) * 0.1;
  ctx.clearRect(0, 0, view.width, view.height);
  drawClusters(time);
  drawEdges(time);
  drawNodes(time);
  window.requestAnimationFrame(drawFrame);
}

function graphBounds() {
  const visible = view.nodes.filter(isVisible);
  if (!visible.length) return { minX: -100, maxX: 100, minY: -100, maxY: 100 };
  return {
    minX: Math.min(...visible.map((item) => item.x)),
    maxX: Math.max(...visible.map((item) => item.x)),
    minY: Math.min(...visible.map((item) => item.y)),
    maxY: Math.max(...visible.map((item) => item.y)),
  };
}

function fitGraph() {
  if (!view.nodes.length) return;
  const bounds = graphBounds();
  const width = Math.max(200, bounds.maxX - bounds.minX + 130);
  const height = Math.max(180, bounds.maxY - bounds.minY + 130);
  view.camera.targetX = (bounds.minX + bounds.maxX) / 2;
  view.camera.targetY = (bounds.minY + bounds.maxY) / 2;
  view.camera.targetZoom = Math.max(0.38, Math.min(1.35, Math.min(view.width / width, view.height / height) * 0.9));
}

function focusNode(item) {
  if (!item) return;
  view.camera.targetX = item.x;
  view.camera.targetY = item.y;
  view.camera.targetZoom = Math.max(0.82, Math.min(1.35, view.camera.targetZoom));
}

function findNodeAt(x, y) {
  let result = null;
  let closest = Number.POSITIVE_INFINITY;
  view.nodes.filter(isVisible).forEach((item) => {
    const point = worldToScreen(item, performance.now());
    const distance = Math.hypot(point.x - x, point.y - y);
    const radius = item.radius * view.camera.zoom + 15;
    if (distance <= radius && distance < closest) {
      result = item;
      closest = distance;
    }
  });
  return result;
}

function canvasPoint(event) {
  const rect = refs.graphCanvas.getBoundingClientRect();
  return { x: event.clientX - rect.left, y: event.clientY - rect.top };
}

function selectNode(item, shouldFocus = false) {
  if (!item) return;
  view.selectedId = item.id;
  if (shouldFocus) focusNode(item);
  if (view.currentKind === "case") renderCaseInspector(view.currentDetails, item);
  else if (view.currentKind === "run") renderRunInspector(view.currentDetails, item);
}

function updateHover(point) {
  const item = findNodeAt(point.x, point.y);
  view.hoverId = item?.id || null;
  refs.graphCanvas.style.cursor = view.pointer ? "grabbing" : item ? "pointer" : "grab";
  if (item) {
    refs.graphTooltip.textContent = `${titleCase(item.kind)} · ${item.label}`;
    refs.graphTooltip.style.left = `${Math.min(view.width - 235, point.x + 14)}px`;
    refs.graphTooltip.style.top = `${Math.min(view.height - 50, point.y + 14)}px`;
    refs.graphTooltip.classList.add("visible");
  } else {
    refs.graphTooltip.classList.remove("visible");
  }
}

function renderTimeline() {
  refs.timelineTrack.replaceChildren();
  view.timeline.forEach((item, index) => {
    const card = el("button", "timeline-card");
    card.type = "button";
    card.dataset.sequence = String(item.sequence);
    card.append(el("b", "", item.label), el("span", "", item.detail));
    card.addEventListener("click", () => {
      stopReplay();
      setActiveTimeline(index);
      const target = view.nodeById.get(item.targetId);
      if (target) selectNode(target, true);
    });
    refs.timelineTrack.append(card);
  });
  setActiveTimeline(view.timeline.length ? view.timeline.length - 1 : -1);
}

function setActiveTimeline(index) {
  [...refs.timelineTrack.children].forEach((card, cardIndex) => {
    card.classList.toggle("active", cardIndex === index);
    if (cardIndex === index) {
      card.setAttribute("aria-current", "step");
      card.scrollIntoView({ block: "nearest", inline: "nearest", behavior: reduceMotion ? "auto" : "smooth" });
    } else {
      card.removeAttribute("aria-current");
    }
  });
}

function stopReplay() {
  if (view.replayTimer) window.clearTimeout(view.replayTimer);
  view.replayTimer = null;
  view.replayPaused = false;
  refs.pauseButton.textContent = "Ⅱ";
}

function replayStep() {
  if (view.replayPaused || view.replayPosition >= view.timeline.length) {
    if (view.replayPosition >= view.timeline.length) stopReplay();
    return;
  }
  const item = view.timeline[view.replayPosition];
  view.playbackCutoff = item.sequence;
  setActiveTimeline(view.replayPosition);
  const target = view.nodeById.get(item.targetId);
  if (target) {
    view.selectedId = target.id;
    focusNode(target);
  }
  view.replayPosition += 1;
  view.replayTimer = window.setTimeout(replayStep, Number(refs.timelineSpeed.value));
}

function startReplay() {
  stopReplay();
  if (!view.timeline.length) return;
  view.replayPosition = 0;
  view.playbackCutoff = 0;
  if (reduceMotion) {
    view.playbackCutoff = Number.POSITIVE_INFINITY;
    setActiveTimeline(view.timeline.length - 1);
    return;
  }
  replayStep();
}

function statusPill(label, tone = "") {
  return el("span", `status-pill ${tone}`.trim(), titleCase(label));
}

function metricCard(value, label) {
  const card = el("div", "stat-card");
  card.append(el("strong", "", value), el("span", "", label));
  return card;
}

function intelSection(title, content) {
  const section = el("section", "intel-section");
  section.append(el("h2", "", title), content);
  return section;
}

function renderCaseIntel(details) {
  const host = hostnameFrom(details.final_url_display || details.seed_url_display);
  const hero = el("section", "intel-hero");
  hero.append(
    el("h1", "", host),
    el("p", "", "Saved one-page public observation. The graph connects only captured pages, verified artifacts, extracted observations, and pending leads."),
  );
  const statuses = el("div", "status-row");
  const adequacyTone = details.capture_adequacy === "adequate" ? "good" : "warn";
  statuses.append(
    statusPill(details.public_status || "saved", details.public_status === "captured" ? "good" : "warn"),
    statusPill(details.capture_adequacy || "legacy capture", adequacyTone),
    statusPill(details.access_outcome || details.capture_outcome || "observed", details.access_outcome === "content" ? "good" : "warn"),
  );
  hero.append(statuses);

  const stats = el("div", "stat-grid");
  stats.append(
    metricCard(details.pages?.length || 0, "Captured pages"),
    metricCard(details.evidence?.length || 0, "Verified artifacts"),
    metricCard(details.observations?.length || 0, "Semantic observations"),
    metricCard(details.candidates?.length || 0, "Pending leads"),
  );

  const limitations = el("ul", "limitation-list");
  const limitValues = [...(details.limitation_reasons || [])];
  if (details.extraction_skip_reason) limitValues.push(details.extraction_skip_reason);
  if (!limitValues.length) limitValues.push("One public page only; no authentication, CAPTCHA bypass, or candidate crawling.");
  limitValues.forEach((reason) => limitations.append(el("li", "", reason)));

  const policy = el("p", "policy-copy", "A candidate is a pending lead, never a confirmed operator or mirror. Similarity is evidence comparison, not ownership probability. Human review remains required.");
  refs.intelContent.replaceChildren(
    hero,
    intelSection("Capture facts", stats),
    intelSection("Known limits", limitations),
    intelSection("Interpretation boundary", policy),
  );
}

function renderRunIntel(details) {
  const hero = el("section", "intel-hero");
  hero.append(
    el("h1", "", valueOr(details.case_id, "Investigation")),
    el("p", "", "A deterministic, append-only investigation replay. Dashed edges are leads; emphasized edges exist only after a recorded human decision."),
  );
  const statuses = el("div", "status-row");
  statuses.append(
    statusPill(details.agent_mode || "deterministic fallback", details.agent_mode === "codex" ? "good" : "warn"),
    statusPill(details.lead_status || "recorded", details.lead_status === "recollected" ? "good" : "warn"),
    statusPill(details.current_assertion_status || "no assertion", details.current_assertion_status === "verified" ? "good" : "warn"),
  );
  hero.append(statuses);
  const stats = el("div", "stat-grid");
  stats.append(
    metricCard(details.graph?.nodes?.length || 0, "Graph nodes"),
    metricCard(details.graph?.edges?.length || 0, "Graph links"),
    metricCard(details.events?.length || 0, "Persisted events"),
    metricCard(details.reviews?.length || 0, "Review versions"),
  );
  const policy = el("p", "policy-copy", "Replay animation is a projection of persisted events. Reloading reconstructs the same graph truth; animation never creates evidence.");
  refs.intelContent.replaceChildren(hero, intelSection("Run facts", stats), intelSection("Evidence rule", policy));
}

function factList(entries) {
  const list = el("dl", "fact-list");
  entries.forEach(([label, value]) => {
    const row = el("div", "fact-row");
    row.append(el("dt", "", label), el("dd", "", valueOr(value)));
    list.append(row);
  });
  return list;
}

function evidenceLink(caseId, record) {
  const link = el("a", "artifact-link", titleCase(record.type));
  link.href = caseArtifactUrl(caseId, record.id);
  link.title = `Open verified artifact ${record.id}`;
  return link;
}

function inspectorHeader(kicker, title, copy) {
  const header = el("header", "inspector-header");
  header.append(el("span", "", kicker), el("h2", "", title));
  if (copy) header.append(el("p", "", copy));
  return header;
}

function evidenceBlock(title, content) {
  const section = el("section", "evidence-block");
  section.append(el("h3", "", title), content);
  return section;
}

function findScreenshot(details, selected) {
  const selectedEvidence = selected?.attributes?.evidence;
  if (selectedEvidence && String(selectedEvidence.type).includes("screenshot")) return selectedEvidence;
  const page = details.pages?.find((item) => `page:${item.id}` === selected?.id) || details.pages?.[0];
  const preferred = page?.screenshot_evidence_id || page?.full_page_screenshot_evidence_id || page?.initial_screenshot_evidence_id;
  return details.evidence?.find((item) => item.id === preferred)
    || details.evidence?.find((item) => String(item.type).includes("screenshot"))
    || null;
}

function renderCaseInspector(details, selected) {
  const screenshot = findScreenshot(details, selected);
  const selectedEvidence = selected?.attributes?.evidence;
  const header = inspectorHeader(
    selected ? titleCase(selected.kind) : "Capture evidence",
    selected?.label || hostnameFrom(details.final_url_display),
    selected?.kind === "candidate_domain" ? evidenceSemantics.candidate : "Evidence shown here is loaded from the verified local case manifest.",
  );
  const children = [header];
  if (screenshot) {
    const preview = el("figure", "evidence-preview");
    const image = el("img");
    image.src = caseArtifactUrl(details.case_id, screenshot.id);
    image.alt = `Captured screenshot evidence for ${hostnameFrom(details.final_url_display)}`;
    image.loading = "eager";
    preview.append(image, el("figcaption", "preview-label", details.capture_adequacy === "adequate" ? "Captured evidence" : "Limited capture"));
    children.push(preview);
  }

  const facts = factList([
    ["Public state", titleCase(details.public_status)],
    ["Adequacy", titleCase(details.capture_adequacy || "legacy capture")],
    ["Access", titleCase(details.access_outcome || details.capture_outcome)],
    ["Extraction", details.extraction_eligible ? "Eligible" : `Withheld · ${valueOr(details.extraction_skip_reason, "capture limit")}`],
    ["Captured", formatTime(selectedEvidence?.collected_at || details.completed_at)],
    ["Dimensions", screenshot?.image_dimensions ? `${screenshot.image_dimensions.width} × ${screenshot.image_dimensions.height}` : null],
  ]);
  children.push(evidenceBlock("Evidence status", facts));

  const artifacts = el("div", "artifact-grid");
  (details.evidence || []).forEach((record) => artifacts.append(evidenceLink(details.case_id, record)));
  children.push(evidenceBlock("Verified artifacts", artifacts));

  const observations = el("div");
  if (details.observations?.length) {
    details.observations.forEach((observation) => {
      const card = el("article", "observation-card");
      card.append(
        el("b", "", titleCase(observation.type)),
        el("strong", "", observation.display_value),
        el("span", "", `${Math.round(observation.confidence * 100)}% confidence · ${titleCase(observation.evidence_strength)}`),
      );
      observations.append(card);
    });
  } else {
    observations.append(el("p", "policy-copy", "Extraction withheld or no semantic observation recorded. This is not an absence claim."));
  }
  children.push(evidenceBlock("Semantic evidence", observations));

  if (details.candidates?.length) {
    const candidates = el("div");
    details.candidates.forEach((candidate) => {
      const card = el("article", "observation-card");
      card.append(el("b", "", "Pending candidate"), el("strong", "", candidate.hostname), el("span", "", evidenceSemantics.candidate));
      candidates.append(card);
    });
    children.push(evidenceBlock("Pending leads", candidates));
  }
  refs.inspectorContent.replaceChildren(...children);
}

function renderReviewForm(details) {
  const form = el("form", "review-form");
  const reviewer = el("input");
  reviewer.name = "reviewer_label";
  reviewer.placeholder = "Reviewer label";
  reviewer.required = true;
  reviewer.maxLength = 200;
  const outcome = el("select");
  ["verified", "rejected", "needs_more_evidence", "duplicate", "uncertain"].forEach((value) => {
    const option = el("option", "", titleCase(value));
    option.value = value;
    outcome.append(option);
  });
  const reason = el("textarea");
  reason.name = "reason";
  reason.placeholder = "Evidence-bounded reason";
  reason.required = true;
  reason.maxLength = 2000;
  const submit = el("button", "", "Append review decision");
  submit.type = "submit";
  form.append(reviewer, outcome, reason, submit);
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    submit.disabled = true;
    submit.textContent = "Saving…";
    try {
      await postJson(`/api/mvp/runs/${encodeURIComponent(details.workspace_id)}/reviews`, {
        assertion_id: details.assertion.assertion_id,
        outcome: outcome.value,
        reviewer_label: reviewer.value,
        reason: reason.value,
      });
      await loadRun(details.workspace_id);
      toast("Append-only review version saved.", "success");
    } catch (error) {
      toast(error.message, "error");
      submit.disabled = false;
      submit.textContent = "Append review decision";
    }
  });
  return form;
}

function renderRunInspector(details, selected) {
  const header = inspectorHeader(
    selected ? titleCase(selected.kind) : "Investigation node",
    selected?.label || details.case_id,
    selected?.status === "lead" ? evidenceSemantics.candidate : "This node is reconstructed from the append-only event stream.",
  );
  const attributes = selected?.attributes || {};
  const facts = factList([
    ["Node state", titleCase(selected?.status)],
    ["Agent", titleCase(details.agent_mode)],
    ["Lead", titleCase(details.lead_status)],
    ["Assertion", titleCase(details.current_assertion_status || "not proposed")],
    ["Run", details.run_id],
  ]);
  const artifactGrid = el("div", "artifact-grid");
  (details.artifacts || []).forEach((artifact) => {
    const link = el("a", "artifact-link", `${artifact.name} · ${artifact.bytes} B`);
    link.href = runArtifactUrl(details.workspace_id, artifact.name);
    artifactGrid.append(link);
  });
  const children = [header, evidenceBlock("Persisted state", facts)];
  if (Object.keys(attributes).length) children.push(evidenceBlock("Node evidence", factList(Object.entries(attributes).slice(0, 8))));
  children.push(evidenceBlock("Run artifacts", artifactGrid));

  if (details.lead_status === "waiting_for_approval") {
    const approve = el("button", "", "Approve bounded Page B recollection");
    approve.type = "button";
    approve.className = "artifact-link";
    approve.addEventListener("click", async () => {
      approve.disabled = true;
      approve.textContent = "Collecting approved fixture…";
      try {
        await postJson(`/api/mvp/runs/${encodeURIComponent(details.workspace_id)}/approve`, {});
        await loadRun(details.workspace_id);
        toast("Approval recorded before bounded recollection.", "success");
      } catch (error) {
        toast(error.message, "error");
        approve.disabled = false;
        approve.textContent = "Approve bounded Page B recollection";
      }
    });
    children.push(evidenceBlock("Approval boundary", approve));
  }
  if (details.assertion) children.push(evidenceBlock("Append human review", renderReviewForm(details)));
  refs.inspectorContent.replaceChildren(...children);
}

function renderError(message) {
  refs.inspectorContent.replaceChildren(inspectorHeader("Unable to load", "Evidence unavailable", message));
  refs.intelContent.replaceChildren(el("section", "intel-hero", message));
  setStatus(message);
}

async function loadCase(caseId) {
  setStatus("Verifying local evidence package…");
  try {
    const details = await requestJson(`/api/cases/${encodeURIComponent(caseId)}`);
    view.currentKind = "case";
    view.currentDetails = details;
    renderCaseIntel(details);
    setGraph(buildCaseProjection(details));
    selectNode(view.nodeById.get(view.selectedId));
    refs.seedInput.value = details.final_url_display || details.seed_url_display || refs.seedInput.value;
    refs.workspaceSelector.value = `case:${caseId}`;
    setStatus(`${hostnameFrom(details.final_url_display)} · manifest verified · ${details.evidence?.length || 0} artifacts`);
  } catch (error) {
    renderError(error.message);
  }
}

async function loadRun(workspaceId) {
  setStatus("Reconstructing append-only event graph…");
  try {
    const details = await requestJson(`/api/mvp/runs/${encodeURIComponent(workspaceId)}`);
    view.currentKind = "run";
    view.currentDetails = details;
    renderRunIntel(details);
    setGraph(buildRunProjection(details));
    selectNode(view.nodeById.get(view.selectedId));
    refs.workspaceSelector.value = `run:${workspaceId}`;
    setStatus(`${details.case_id} · ${details.events?.length || 0} persisted events · ${titleCase(details.lead_status)}`);
  } catch (error) {
    renderError(error.message);
  }
}

function renderSelector() {
  refs.workspaceSelector.replaceChildren();
  const cases = view.cases.filter((item) => item.integrity === "verified");
  if (cases.length) {
    const group = el("optgroup");
    group.label = "Saved public captures";
    cases.forEach((item) => {
      const option = el("option", "", `${hostnameFrom(item.final_url_display)} · ${titleCase(item.capture_adequacy || "legacy")}`);
      option.value = `case:${item.case_id}`;
      group.append(option);
    });
    refs.workspaceSelector.append(group);
  }
  if (view.runs.length) {
    const group = el("optgroup");
    group.label = "Reviewable investigations";
    view.runs.forEach((item) => {
      const option = el("option", "", `${valueOr(item.case_id)} · ${titleCase(item.lead_status)}`);
      option.value = `run:${item.workspace_id}`;
      group.append(option);
    });
    refs.workspaceSelector.append(group);
  }
  if (!cases.length && !view.runs.length) {
    const option = el("option", "", "No saved evidence yet");
    option.value = "";
    refs.workspaceSelector.append(option);
  }
}

async function refreshIndexes() {
  const [casesResult, runsResult] = await Promise.allSettled([
    requestJson("/api/cases"),
    requestJson("/api/mvp/runs"),
  ]);
  view.cases = casesResult.status === "fulfilled" ? casesResult.value.cases || [] : [];
  view.runs = runsResult.status === "fulfilled" ? runsResult.value.runs || [] : [];
  renderSelector();
}

async function loadCapability() {
  try {
    const status = await requestJson("/api/mvp/capabilities");
    if (status.state === "codex_ready") {
      refs.capabilityState.classList.add("ready");
      refs.capabilityState.lastChild.textContent = "Codex ready";
    } else {
      refs.capabilityState.classList.remove("ready");
      refs.capabilityState.lastChild.textContent = "Safe fallback";
    }
  } catch {
    refs.capabilityState.classList.remove("ready");
    refs.capabilityState.lastChild.textContent = "Local only";
  }
}

async function boot() {
  refs.seedInput.value = ["https", "://", "qq101xfw.com"].join("");
  await refreshIndexes();
  void loadCapability();
  const verified = view.cases.filter((item) => item.integrity === "verified");
  const preferred = verified.find((item) => item.final_url_display?.includes("qq101xfw.com"))
    || verified.find((item) => item.final_url_display?.includes("qq888bet4cv.com"))
    || verified[0];
  if (preferred) await loadCase(preferred.case_id);
  else if (view.runs[0]) await loadRun(view.runs[0].workspace_id);
  else setStatus("Enter one public URL to create a bounded observation.");
}

refs.scanForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const seedUrl = refs.seedInput.value.trim();
  refs.scanButton.disabled = true;
  refs.scanButton.textContent = "Scanning…";
  setStatus("One page · no clicks · no candidate crawling…");
  try {
    const details = await postJson("/api/cases", { seed_url: seedUrl });
    await refreshIndexes();
    await loadCase(details.case_id);
    toast("Bounded public capture saved and verified.", "success");
  } catch (error) {
    toast(error.message, "error");
    setStatus(`Capture stopped safely · ${error.message}`);
  } finally {
    refs.scanButton.disabled = false;
    refs.scanButton.replaceChildren(el("span", "", "→"), document.createTextNode(" Scan"));
  }
});

refs.workspaceSelector.addEventListener("change", () => {
  const [kind, id] = refs.workspaceSelector.value.split(":", 2);
  if (kind === "case" && id) void loadCase(id);
  if (kind === "run" && id) void loadRun(id);
});

refs.graphSearch.addEventListener("input", () => {
  view.query = refs.graphSearch.value.trim().toLowerCase();
  view.searchIds.clear();
  if (!view.query) return;
  view.nodes.forEach((item) => {
    const haystack = `${item.label} ${item.kind} ${item.status} ${item.cluster}`.toLowerCase();
    if (haystack.includes(view.query)) view.searchIds.add(item.id);
  });
  const first = view.nodes.find((item) => view.searchIds.has(item.id));
  if (first) focusNode(first);
});

refs.graphCanvas.addEventListener("pointerdown", (event) => {
  const point = canvasPoint(event);
  const item = findNodeAt(point.x, point.y);
  refs.graphCanvas.setPointerCapture(event.pointerId);
  view.pointer = {
    id: event.pointerId,
    startX: point.x,
    startY: point.y,
    cameraX: view.camera.targetX,
    cameraY: view.camera.targetY,
    moved: false,
  };
  view.dragNode = item;
  if (item) item.pinned = true;
  refs.graphCanvas.classList.add("dragging");
});

refs.graphCanvas.addEventListener("pointermove", (event) => {
  const point = canvasPoint(event);
  if (!view.pointer || view.pointer.id !== event.pointerId) {
    updateHover(point);
    return;
  }
  const dx = point.x - view.pointer.startX;
  const dy = point.y - view.pointer.startY;
  view.pointer.moved ||= Math.hypot(dx, dy) > 4;
  if (view.dragNode) {
    const world = screenToWorld(point.x, point.y);
    view.dragNode.x = world.x;
    view.dragNode.y = world.y;
    view.dragNode.tx = world.x;
    view.dragNode.ty = world.y;
  } else {
    view.camera.targetX = view.pointer.cameraX - dx / view.camera.zoom;
    view.camera.targetY = view.pointer.cameraY - dy / view.camera.zoom;
  }
});

function endPointer(event) {
  if (!view.pointer || view.pointer.id !== event.pointerId) return;
  const selected = view.dragNode;
  const wasMoved = view.pointer.moved;
  if (selected) selected.pinned = wasMoved;
  view.pointer = null;
  view.dragNode = null;
  refs.graphCanvas.classList.remove("dragging");
  if (selected && !wasMoved) selectNode(selected, false);
}

refs.graphCanvas.addEventListener("pointerup", endPointer);
refs.graphCanvas.addEventListener("pointercancel", endPointer);
refs.graphCanvas.addEventListener("pointerleave", () => {
  if (!view.pointer) refs.graphTooltip.classList.remove("visible");
});

refs.graphCanvas.addEventListener("wheel", (event) => {
  event.preventDefault();
  const point = canvasPoint(event);
  const before = screenToWorld(point.x, point.y);
  const factor = event.deltaY > 0 ? 0.88 : 1.13;
  const nextZoom = Math.max(0.26, Math.min(2.6, view.camera.targetZoom * factor));
  view.camera.targetZoom = nextZoom;
  const afterX = (point.x - view.width / 2) / nextZoom + view.camera.targetX;
  const afterY = (point.y - view.height / 2) / nextZoom + view.camera.targetY;
  view.camera.targetX += before.x - afterX;
  view.camera.targetY += before.y - afterY;
}, { passive: false });

refs.zoomIn.addEventListener("click", () => { view.camera.targetZoom = Math.min(2.6, view.camera.targetZoom * 1.2); });
refs.zoomOut.addEventListener("click", () => { view.camera.targetZoom = Math.max(0.26, view.camera.targetZoom / 1.2); });
refs.fitGraph.addEventListener("click", fitGraph);
refs.replayButton.addEventListener("click", startReplay);
refs.pauseButton.addEventListener("click", () => {
  if (!view.replayTimer && view.playbackCutoff === Number.POSITIVE_INFINITY) return;
  view.replayPaused = !view.replayPaused;
  refs.pauseButton.textContent = view.replayPaused ? "▶" : "Ⅱ";
  if (!view.replayPaused) replayStep();
});

const resizeObserver = new ResizeObserver(() => {
  resizeCanvas();
  fitGraph();
});
resizeObserver.observe(refs.graphCanvas);
resizeCanvas();
window.requestAnimationFrame(drawFrame);
void boot();
