"use strict";

const refs = {
  scanForm: document.getElementById("scan-form"),
  seedInput: document.getElementById("seed-url"),
  scanButton: document.getElementById("scan-button"),
  workspaceSelector: document.getElementById("workspace-selector"),
  capabilityState: document.getElementById("capability-state"),
  intelContent: document.getElementById("intel-content"),
  graphCanvas: document.getElementById("graph-canvas"),
  graphMinimap: document.getElementById("graph-minimap"),
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
  landingView: document.getElementById("landing-view"),
  scanView: document.getElementById("scan-view"),
  workspaceView: document.getElementById("workspace-view"),
  summaryView: document.getElementById("summary-view"),
  workspaceCommand: document.getElementById("workspace-command"),
  workspaceTitle: document.getElementById("workspace-title"),
  workspaceUrl: document.getElementById("workspace-url"),
  recentCases: document.getElementById("recent-cases"),
  caseSearch: document.getElementById("case-search"),
  caseSort: document.getElementById("case-sort"),
  caseFilters: Array.from(document.querySelectorAll("[data-case-filter]")),
  caseGridView: document.getElementById("case-grid-view"),
  caseListView: document.getElementById("case-list-view"),
  investigationName: document.getElementById("investigation-name"),
  captureProgress: document.getElementById("capture-progress"),
  progressKicker: document.getElementById("progress-kicker"),
  progressTitle: document.getElementById("progress-title"),
  progressDetail: document.getElementById("progress-detail"),
  progressElapsed: document.getElementById("progress-elapsed"),
  progressStages: document.getElementById("progress-stages"),
  scanPages: document.getElementById("scan-pages"),
  scanEvidence: document.getElementById("scan-evidence"),
  scanBudget: document.getElementById("scan-budget"),
  scanQueue: document.getElementById("scan-queue"),
  scanActivity: document.getElementById("scan-activity"),
  scanTechnical: document.getElementById("scan-technical"),
  scanWorkspaceButton: document.getElementById("scan-workspace-button"),
  brandHome: document.getElementById("brand-home"),
  landingNewInvestigation: document.getElementById("landing-new-investigation"),
  newInvestigation: document.getElementById("new-investigation"),
  openSummary: document.getElementById("open-summary"),
  backToGraph: document.getElementById("back-to-graph"),
  summaryContent: document.getElementById("summary-content"),
  summarySubtitle: document.getElementById("summary-subtitle"),
  timelineScrubber: document.getElementById("timeline-scrubber"),
  timelineCurrentTime: document.getElementById("timeline-current-time"),
  timelineMode: document.getElementById("timeline-mode"),
  inspectorTabs: Array.from(document.querySelectorAll("[data-inspector-tab]")),
};

const evidenceSemantics = {
  candidate: "Relationship: not determined",
  comparison: "Evidence-similarity score",
  accessibility: "accessible relationship table",
  current: "aria-current",
};

const investigationStages = [
  { label: "Validate target", stages: ["queued", "validating_seed", "launching_browser"] },
  { label: "Capture pages", stages: ["initializing_case", "capturing_page"] },
  { label: "Preserve & extract", stages: ["preserving_artifacts", "running_ocr", "extracting_evidence", "page_completed", "generating_candidates", "finalizing_case"] },
  { label: "Bounded investigation", stages: ["verifying_evidence", "running_agent"] },
  { label: "Classify & graph", stages: ["classifying_indicators", "building_graph"] },
  { label: "Finalize case", stages: ["completed"] },
];

const investigationStageCopy = {
  queued: ["Preparing isolated workspace", "A single local investigation slot has been reserved."],
  validating_seed: ["Validating public destination", "Checking scheme, destination, and read-only collection policy."],
  launching_browser: ["Launching isolated browser", "Starting a killable browser worker with a hard wall-clock boundary."],
  initializing_case: ["Creating immutable case record", "Recording scope, page budget, depth, and the normalized seed."],
  capturing_page: ["Capturing rendered page", "Waiting for visible render stability and collecting same-site public navigation."],
  preserving_artifacts: ["Preserving source artifacts", "Saving initial, canonical, and full-page screenshots with rendered HTML and response facts."],
  running_ocr: ["Checking screenshot text", "Running bounded local OCR as supplemental evidence; OCR never replaces source artifacts."],
  extracting_evidence: ["Extracting public OSINT evidence", "Linking public contacts, offers, payments, destinations, and claims to page evidence."],
  page_completed: ["Page evidence committed", "The current page record and evidence references are now persisted."],
  generating_candidates: ["Generating reviewable leads", "Comparing verified evidence without treating similarity as ownership probability."],
  finalizing_case: ["Finalizing case package", "Writing the manifest and truthful capture limitations."],
  verifying_evidence: ["Re-verifying saved artifacts", "Checking the completed case package before the agent can inspect it."],
  running_agent: ["Running policy-gated exploration", "Planning safe public interactions with deterministic fallback and recorded tool events."],
  classifying_indicators: ["Classifying judol indicators", "Counting evidence-backed text/entity indicators without percentages or verdicts."],
  building_graph: ["Building event-sourced graph", "Reducing persisted pages, observations, leads, and actions into the investigation view."],
  completed: ["Investigation ready", "The saved case, graph, screenshots, evidence, and timeline are ready for review."],
  failed: ["Investigation stopped safely", "The failure boundary was recorded; no result is presented as a completed capture."],
};

const ctx = refs.graphCanvas.getContext("2d", { alpha: true });
const miniCtx = refs.graphMinimap.getContext("2d", { alpha: true });
const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
const colors = {
  case: "#ed1764",
  domain: "#ed1764",
  page: "#ed1764",
  seed_page: "#ed1764",
  collected_page: "#ed1764",
  screenshot: "#ef80c2",
  document: "#8b95a7",
  readiness: "#32b9e8",
  observation: "#8b95a7",
  public_contact: "#00b4a6",
  public_claim: "#f2c94c",
  external_destination: "#32b9e8",
  redirect_target: "#32b9e8",
  candidate: "#8a5cf6",
  candidate_domain: "#8a5cf6",
  claimed_brand: "#ff8a00",
  default: "#8b95a7",
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
  activeJobId: null,
  jobPolling: false,
  progressClock: null,
  caseFilter: "all",
  caseQuery: "",
  caseLayout: "grid",
  nodeFilters: new Set(["page", "contact", "brand", "transaction", "offer", "destination", "candidate", "other"]),
  selectedEvidenceId: null,
  scanWorkspaceId: null,
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
  return valueOr(value).replaceAll("_", " ").replaceAll(".", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function shortText(value, length = 34) {
  const text = valueOr(value, "Untitled");
  return text.length <= length ? text : `${text.slice(0, length - 1)}…`;
}

function formatTime(value) {
  if (!value) return "Time not recorded";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return String(value);
  return new Intl.DateTimeFormat("en-GB", {
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
    timeZone: "Asia/Jakarta",
  }).format(parsed);
}

function exactTime(value) {
  if (!value) return "Time not recorded";
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? String(value) : `${parsed.toISOString()} · source ${String(value)}`;
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

function showScreen(name) {
  refs.landingView.hidden = name !== "landing";
  refs.scanView.hidden = name !== "scan";
  refs.workspaceView.hidden = name !== "workspace";
  refs.summaryView.hidden = name !== "summary";
  refs.workspaceCommand.hidden = !["workspace", "summary"].includes(name);
  refs.landingNewInvestigation.hidden = name !== "landing";
  document.body.dataset.screen = name;
  if (name === "workspace") {
    resizeCanvas();
    fitGraph();
    for (let step = 0; step < 12; step += 1) physicsStep(16);
    paintFrame(performance.now());
  }
  window.scrollTo({ top: 0, behavior: reduceMotion ? "auto" : "smooth" });
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

function wait(milliseconds) {
  return new Promise((resolve) => window.setTimeout(resolve, milliseconds));
}

function formatElapsed(startedAt) {
  const started = new Date(startedAt).getTime();
  const elapsedSeconds = Math.max(0, Math.floor((Date.now() - started) / 1000));
  const minutes = String(Math.floor(elapsedSeconds / 60)).padStart(2, "0");
  const seconds = String(elapsedSeconds % 60).padStart(2, "0");
  return `${minutes}:${seconds}`;
}

function progressDetail(stage, detail = {}) {
  if (stage === "capturing_page" && detail.page_id) {
    return `${detail.page_id} · depth ${detail.depth || 0} · ${detail.queued_pages || 0} page(s) queued`;
  }
  if (stage === "preserving_artifacts" && detail.page_id) return `${detail.page_id} · screenshot, text, response, readiness, and HTML evidence`;
  if (stage === "running_ocr" && detail.page_id) return `${detail.page_id} · bounded supplemental OCR check`;
  if (stage === "extracting_evidence" && detail.page_id) return `${detail.page_id} · evidence-linked public entities and observations`;
  if (stage === "page_completed" && detail.page_id) return `${detail.page_id} · ${detail.observations || 0} observation(s) persisted · ${titleCase(detail.adequacy)}`;
  if (stage === "generating_candidates") return `${detail.page_count || 0} captured page(s) · ${detail.observation_count || 0} public observation(s)`;
  if (stage === "finalizing_case") return `${detail.page_count || 0} page(s) · ${detail.candidate_count || 0} candidate lead(s)`;
  if (stage === "classifying_indicators") return `${detail.observation_count || 0} public observation(s) under evidence-count policy`;
  return investigationStageCopy[stage]?.[1] || "Recording the current bounded operation.";
}

function investigationGroupIndex(stage) {
  return investigationStages.findIndex((group) => group.stages.includes(stage));
}

function stageGlyph(stage) {
  if (["validating_seed", "verifying_evidence"].includes(stage)) return "✓";
  if (["capturing_page", "preserving_artifacts", "initializing_case"].includes(stage)) return "▤";
  if (["running_ocr", "extracting_evidence", "classifying_indicators"].includes(stage)) return "◉";
  if (["running_agent", "generating_candidates"].includes(stage)) return "◇";
  if (stage === "building_graph") return "⌘";
  if (stage === "failed") return "!";
  if (stage === "completed") return "✓";
  return "·";
}

function renderInvestigationProgress(job) {
  showScreen("scan");
  const [title] = investigationStageCopy[job.stage] || [titleCase(job.stage)];
  refs.progressKicker.textContent = job.status === "failed" ? "CAPTURE STOPPED" : job.status === "completed" ? "EVIDENCE SAVED" : "INVESTIGATION ACTIVE";
  refs.progressTitle.textContent = title;
  refs.progressDetail.textContent = job.error || progressDetail(job.stage, job.detail);
  refs.progressElapsed.textContent = formatElapsed(job.started_at);
  const history = job.history || [];
  const currentGroup = job.stage === "failed"
    ? Math.max(0, ...history.map((item) => investigationGroupIndex(item.stage)))
    : investigationGroupIndex(job.stage);
  refs.progressStages.replaceChildren(...investigationStages.map((group, index) => {
    const item = el("li", "progress-stage", group.label);
    item.dataset.step = String(index + 1);
    if (index < currentGroup || job.status === "completed") item.classList.add("reached");
    if (index === currentGroup && job.status !== "completed") {
      item.classList.add("active");
      if (job.status === "failed") item.classList.add("failed");
      item.setAttribute("aria-current", "step");
    }
    return item;
  }));

  const resultPages = job.result?.source_case?.pages || job.result?.pages || [];
  const preservedPages = history.filter((item) => item.stage === "preserving_artifacts").length;
  const resultObservations = job.result?.source_case?.observations || job.result?.observations;
  const observedCount = Array.isArray(resultObservations)
    ? resultObservations.length
    : Number.isInteger(job.detail?.observation_count) ? job.detail.observation_count : null;
  refs.scanPages.textContent = String(resultPages.length || preservedPages);
  refs.scanEvidence.textContent = observedCount === null ? "—" : String(observedCount);
  refs.scanQueue.textContent = job.status === "completed" ? "0" : Number.isInteger(job.detail?.queued_pages) ? String(job.detail.queued_pages) : "—";
  refs.scanBudget.textContent = "115s";

  const activity = history.slice(-24).map((entry, index) => {
    const row = el("article", "activity-item");
    const icon = el("span", "activity-item-icon", stageGlyph(entry.stage));
    const label = investigationStageCopy[entry.stage]?.[0] || titleCase(entry.stage);
    const detail = entry.stage === job.stage
      ? progressDetail(entry.stage, job.detail)
      : investigationStageCopy[entry.stage]?.[1] || "Persisted bounded stage transition.";
    const time = el("time", "", formatTime(entry.at));
    time.dateTime = entry.at || "";
    time.title = exactTime(entry.at);
    row.append(icon, el("strong", "", label), el("p", "", detail), time);
    row.style.animationDelay = `${Math.min(index * 20, 180)}ms`;
    return row;
  });
  refs.scanActivity.replaceChildren(...activity);
  refs.scanTechnical.replaceChildren(...history.slice(-12).map((entry) => {
    const item = el("span", "technical-event", `${titleCase(entry.stage)} · ${formatTime(entry.at)}`);
    item.title = exactTime(entry.at);
    return item;
  }));

  view.scanWorkspaceId = job.result?.workspace_id || null;
  refs.scanWorkspaceButton.disabled = !view.scanWorkspaceId;
  refs.scanWorkspaceButton.textContent = view.scanWorkspaceId ? "Open evidence workspace →" : "Workspace unavailable";
  if (view.progressClock) window.clearInterval(view.progressClock);
  if (["queued", "running"].includes(job.status)) {
    view.progressClock = window.setInterval(() => {
      refs.progressElapsed.textContent = formatElapsed(job.started_at);
    }, 1000);
  }
}

function setScanActive(active) {
  document.body.dataset.scanning = active ? "true" : "false";
  refs.scanButton.disabled = active;
  refs.seedInput.disabled = active;
  refs.investigationName.disabled = active;
  refs.scanButton.replaceChildren(
    document.createTextNode(active ? "Investigation active " : "Start investigation "),
    el("span", "", active ? "•••" : "→"),
  );
  if (!active && view.progressClock) {
    window.clearInterval(view.progressClock);
    view.progressClock = null;
  }
}

async function monitorInvestigationJob(jobId) {
  if (view.jobPolling && view.activeJobId === jobId) return;
  view.activeJobId = jobId;
  view.jobPolling = true;
  setScanActive(true);
  showScreen("scan");
  const clientDeadline = Date.now() + 165000;
  let latestJob = null;
  try {
    while (Date.now() < clientDeadline) {
      const job = await requestJson(`/api/investigation-jobs/${encodeURIComponent(jobId)}`);
      latestJob = job;
      renderInvestigationProgress(job);
      setStatus(`${investigationStageCopy[job.stage]?.[0] || titleCase(job.stage)} · ${formatElapsed(job.started_at)} elapsed`);
      if (job.status === "completed") {
        await refreshIndexes();
        await wait(reduceMotion ? 0 : 420);
        await loadRun(job.result.workspace_id);
        toast("Public capture, OSINT indicators, graph, and timeline saved.", "success");
        return;
      }
      if (job.status === "failed") throw new Error(job.error || "Investigation stopped safely");
      await wait(650);
    }
    throw new Error("The UI stopped waiting after 165 seconds; reload to recover the server-side job state.");
  } catch (error) {
    const failedJob = {
      status: "failed",
      stage: "failed",
      started_at: latestJob?.started_at || new Date().toISOString(),
      history: latestJob?.history || [],
      detail: {},
      error: error.message,
    };
    renderInvestigationProgress(failedJob);
    toast(error.message, "error");
    setStatus(`Capture stopped safely · ${error.message}`);
  } finally {
    view.jobPolling = false;
    view.activeJobId = null;
    setScanActive(false);
  }
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
  if (["observation", "public_contact", "public_claim", "claimed_brand"].includes(kind)) return "Public observations";
  if (["candidate", "candidate_domain", "external_destination", "redirect_target"].includes(kind)) return "Pending leads";
  return "Evidence graph";
}

function presentationFor(item) {
  const kind = typeof item === "string" ? item : item.kind;
  const attributes = typeof item === "string" ? {} : item.attributes || {};
  const observation = attributes.observation || {};
  const observationType = String(attributes.observation_type || observation.type || observation.observation_type || "");
  const category = String(attributes.claim_category || "").toLowerCase();
  if (["case", "domain", "page", "seed_page", "collected_page"].includes(kind)) {
    return { visualKind: "page", label: "Page", color: "#ed1764", icon: "▤", shape: "roundSquare" };
  }
  if (kind === "public_contact") {
    if (observationType.includes("whatsapp")) return { visualKind: "contact", label: "WhatsApp", color: "#00b4a6", icon: "WA", shape: "circle" };
    if (observationType.includes("telegram")) return { visualKind: "contact", label: "Telegram", color: "#00b4a6", icon: "TG", shape: "circle" };
    if (observationType.includes("email")) return { visualKind: "contact", label: "Email", color: "#00b4a6", icon: "@", shape: "circle" };
    if (observationType.includes("phone")) return { visualKind: "contact", label: "Phone", color: "#00b4a6", icon: "TEL", shape: "circle" };
    return { visualKind: "contact", label: "Contact", color: "#00b4a6", icon: "ID", shape: "circle" };
  }
  if (kind === "claimed_brand") return { visualKind: "brand", label: "Claimed brand", color: "#ff8a00", icon: "◇", shape: "hex" };
  if (kind === "public_claim" && (category.includes("payment") || category.includes("transaction"))) {
    return { visualKind: "transaction", label: "Transaction", color: "#ff8a00", icon: "$", shape: "hex" };
  }
  if (kind === "public_claim" && category.includes("offer")) {
    return { visualKind: "offer", label: "Offer", color: "#f2c94c", icon: "%", shape: "hex" };
  }
  if (["external_destination", "redirect_target"].includes(kind)) {
    return { visualKind: "destination", label: kind === "redirect_target" ? "Redirect" : "Destination", color: "#32b9e8", icon: kind === "redirect_target" ? "↪" : "↗", shape: "diamond" };
  }
  if (["candidate", "candidate_domain"].includes(kind)) {
    return { visualKind: "candidate", label: "Candidate", color: "#8a5cf6", icon: "☆", shape: "diamond" };
  }
  return { visualKind: "other", label: "Other evidence", color: "#8b95a7", icon: "···", shape: "circle" };
}

function nodeCode(item) {
  return presentationFor(item).icon;
}

function radiusFor(kind, primary) {
  if (primary) return 19;
  if (["case", "domain", "page", "seed_page", "collected_page"].includes(kind)) return 14;
  return 11;
}

function normalizeNode(raw, index, extras = {}) {
  const kind = nodeKind(raw.kind || raw.type);
  const node = {
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
  node.presentation = presentationFor(node);
  return node;
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
  const pages = details.pages || [];
  const primaryPage = pages[0];
  const pageIds = new Map();
  pages.forEach((page, index) => {
    const nodeId = `page:${page.id}`;
    pageIds.set(page.id, nodeId);
    addUniqueNode(nodes, normalizeNode({
      id: nodeId,
      type: index === 0 ? "seed_page" : "collected_page",
      label: page.final_url_display,
      status: "collected",
    }, index, {
      primary: index === 0,
      sequence: index + 1,
      attributes: { page, source_case_id: details.case_id },
      cluster: "Captured pages",
    }));
    if (index > 0 && primaryPage) {
      addUniqueEdge(edges, normalizeEdge({
        id: `crawl:${primaryPage.id}:${page.id}`,
        source: `page:${primaryPage.id}`,
        target: nodeId,
        relation: "crawled same-site page",
      }, edges.length, { sequence: index + 1 }));
    }
  });
  if (!nodes.length) {
    addUniqueNode(nodes, normalizeNode({
      id: `page:${details.case_id}`,
      type: "seed_page",
      label: details.final_url_display || details.seed_url_display,
      status: "collected",
    }, 0, { primary: true, sequence: 1, attributes: { source_case_id: details.case_id } }));
  }
  const rootId = pageIds.get(primaryPage?.id) || nodes[0].id;
  let sequence = Math.max(2, pages.length + 1);
  timeline.push({
    sequence: 1,
    label: "Capture started",
    detail: formatTime(details.started_at),
    occurredAt: details.started_at,
    targetId: rootId,
  });
  pages.forEach((page, index) => timeline.push({
    sequence: index + 2,
    label: index === 0 ? "Seed page captured" : "Same-site page captured",
    detail: `${titleCase(page.capture_adequacy)} · ${hostnameFrom(page.final_url_display)}`,
    targetId: pageIds.get(page.id),
  }));

  const knownByHost = new Map(
    view.cases
      .filter((item) => item.integrity === "verified")
      .map((item) => [hostnameFrom(item.final_url_display), item]),
  );
  const sourceHost = hostnameFrom(details.final_url_display || details.seed_url_display);
  const token = sourceHost.match(/[a-z]+\d+|\d+[a-z]+|\d{3,}/i)?.[0]?.toLowerCase() || "";
  const candidateHosts = new Set((details.candidates || []).map((item) => item.hostname));
  const destinations = new Map();
  const addDestination = (url, sourcePageId, source, redirect = false) => {
    const host = hostnameFrom(url);
    if (!host || host === sourceHost) return;
    const known = knownByHost.get(host);
    const related = Boolean(known || candidateHosts.has(host) || (token && host.includes(token)));
    if (!related) return;
    const existing = destinations.get(host) || { host, url, sourcePageId, sources: [], redirect, known };
    existing.sources.push(source);
    existing.known ||= known;
    existing.redirect ||= redirect;
    destinations.set(host, existing);
  };
  (details.frontier || []).forEach((item) => {
    if (item.normalized_url_display) addDestination(
      item.normalized_url_display,
      item.source_page_id,
      { frontier: item },
      item.discovery_method === "redirect",
    );
  });
  (details.observations || []).forEach((observation) => {
    if (["public_outgoing_link", "public_redirect_target"].includes(observation.type)) {
      addDestination(
        observation.display_value,
        observation.source_page_id,
        { observation },
        observation.type === "public_redirect_target",
      );
    }
  });
  destinations.forEach((destination) => {
    sequence += 1;
    const nodeId = `destination:${destination.host}`;
    const status = destination.known ? "collected" : "lead";
    addUniqueNode(nodes, normalizeNode({
      id: nodeId,
      type: destination.redirect ? "redirect_target" : destination.known ? "external_destination" : "candidate_domain",
      label: destination.host,
      status,
    }, nodes.length, {
      sequence,
      status,
      cluster: "Linked destinations",
      attributes: {
        url: destination.url,
        observations: destination.sources,
        matched_case_id: destination.known?.case_id,
        relationship: destination.known ? "observed link to saved capture" : evidenceSemantics.candidate,
      },
    }));
    const sourceId = pageIds.get(destination.sourcePageId) || rootId;
    addUniqueEdge(edges, normalizeEdge({
      id: `destination-edge:${sourceId}:${nodeId}`,
      source: sourceId,
      target: nodeId,
      relation: destination.redirect ? "publicly redirects to" : "publicly links to",
    }, edges.length, { sequence, appearance: status === "lead" ? "dashed" : "solid_emphasized" }));
    timeline.push({
      sequence,
      label: destination.known ? "Saved destination matched" : "Candidate lead observed",
      detail: destination.host,
      targetId: nodeId,
    });
  });

  const contactTypes = new Set([
    "public_telegram_alias",
    "public_telegram_contact",
    "public_whatsapp_link",
    "public_phone_number",
    "public_email_address",
  ]);
  const claimCategories = new Map([
    ["public_payment_method", "Payment indicators"],
    ["public_payment_provider", "Payment indicators"],
    ["public_offer_claim", "Offer claims"],
    ["public_legal_or_license_claim", "Legal claims"],
    ["public_referral_code", "Referral markers"],
    ["public_tracking_identifier", "Tracking markers"],
  ]);
  const directSignals = (details.observations || []).filter((item) => (
    item.type === "claimed_brand_identity" || contactTypes.has(item.type)
  )).slice(0, 18);
  directSignals.forEach((observation) => {
    sequence += 1;
    const kind = observation.type === "claimed_brand_identity" ? "claimed_brand" : "public_contact";
    const nodeId = `observation:${observation.id}`;
    addUniqueNode(nodes, normalizeNode({
      id: nodeId,
      type: kind,
      label: observation.display_value,
      status: "observed",
    }, nodes.length, {
      sequence,
      cluster: "Public observations",
      attributes: { observation },
    }));
    const sourceId = pageIds.get(observation.source_page_id) || rootId;
    addUniqueEdge(edges, normalizeEdge({
      id: `observed:${sourceId}:${nodeId}`,
      source: sourceId,
      target: nodeId,
      relation: observation.type === "claimed_brand_identity" ? "claims brand" : "publishes public contact",
    }, edges.length, { sequence }));
    timeline.push({
      sequence,
      label: titleCase(observation.type),
      detail: "Evidence-backed semantic observation",
      targetId: nodeId,
    });
  });

  const claimGroups = new Map();
  (details.observations || []).forEach((observation) => {
    const category = claimCategories.get(observation.type);
    if (!category) return;
    const sourceId = pageIds.get(observation.source_page_id) || rootId;
    const key = `${sourceId}:${category}`;
    const group = claimGroups.get(key) || { sourceId, category, values: [], observations: [] };
    if (!group.values.includes(observation.display_value)) group.values.push(observation.display_value);
    group.observations.push(observation);
    claimGroups.set(key, group);
  });
  claimGroups.forEach((group) => {
    sequence += 1;
    const nodeId = `claim:${group.sourceId}:${group.category.toLowerCase().replaceAll(" ", "-")}`;
    addUniqueNode(nodes, normalizeNode({
      id: nodeId,
      type: "public_claim",
      label: `${group.category} · ${group.values.slice(0, 4).join(", ")}`,
      status: "observed",
    }, nodes.length, {
      sequence,
      cluster: "Public observations",
      attributes: { claim_category: group.category, values: group.values, observations: group.observations },
    }));
    addUniqueEdge(edges, normalizeEdge({
      id: `claim-edge:${group.sourceId}:${nodeId}`,
      source: group.sourceId,
      target: nodeId,
      relation: "displays public claim",
    }, edges.length, { sequence }));
    timeline.push({
      sequence,
      label: group.category,
      detail: `${group.values.length} evidence-backed public claim${group.values.length === 1 ? "" : "s"}`,
      targetId: nodeId,
    });
  });

  (details.evidence || [])
    .filter((record) => String(record.type).includes("screenshot"))
    .forEach((record) => {
      sequence += 1;
      timeline.push({
        sequence,
        label: titleCase(record.type),
        detail: `${formatTime(record.collected_at)} · saved image evidence`,
        occurredAt: record.collected_at,
        targetId: pageIds.get(record.page_id) || rootId,
      });
    });
  timeline.push({
    sequence: sequence + 1,
    label: details.capture_adequacy === "adequate" ? "Capture adequate" : "Capture limited",
    detail: `${titleCase(details.extraction_tier || "none")} evidence · ${formatTime(details.completed_at)}`,
    occurredAt: details.completed_at,
    targetId: rootId,
  });
  return { nodes, edges, timeline, mode: "Public evidence relations" };
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
    cluster: ["external_destination", "redirect_target", "candidate_domain"].includes(raw.kind)
      ? "Linked destinations"
      : undefined,
  }));
  const edges = (details.graph?.edges || []).map((raw, index) => normalizeEdge(raw, index, {
    sequence: Math.min(...(raw.supporting_event_ids || []).map((id) => eventSequence.get(id) || 999), index + 2),
  }));
  const observationEvents = (details.events || []).filter((event) => event.kind === "observation.created");
  const blockedPreflights = (details.events || []).filter(
    (event) => event.kind === "tool.blocked" && event.payload?.policy_preflight,
  );
  let observationsAdded = false;
  let blockedPreflightsAdded = false;
  const timeline = [];
  (details.events || []).forEach((event) => {
    if (event.kind === "interactive_element.discovered") return;
    if (event.kind === "tool.requested" && (event.payload?.executed === false || event.payload?.action === "policy_preflight")) return;
    if (event.kind === "tool.blocked" && event.payload?.policy_preflight) {
      if (blockedPreflightsAdded) return;
      blockedPreflightsAdded = true;
      timeline.push({
        sequence: event.sequence,
        label: `${blockedPreflights.length} unsafe controls blocked`,
        detail: "Policy preflight only · never executed",
        occurredAt: event.occurred_at,
        targetId: null,
        event,
      });
      return;
    }
    if (event.kind === "entity.matched") return;
    if (event.kind === "observation.created") {
      if (observationsAdded) return;
      observationsAdded = true;
      timeline.push({
        sequence: event.sequence,
        label: "Semantic evidence extracted",
        detail: `${observationEvents.length} evidence-backed observations`,
        occurredAt: event.occurred_at,
        targetId: (details.graph?.animations || []).find((item) => item.sequence === event.sequence)?.target_id || null,
        event,
      });
      return;
    }
    const labelByKind = {
      "run.started": "Investigation started",
      "collection.started": "Bounded crawl started",
      "artifact.captured": event.payload?.interaction_artifact ? "Interaction evidence saved" : "Page evidence saved",
      "agent.objective.created": "Agent objective issued",
      "agent.fallback.activated": "Safe fallback activated",
      "tool.requested": "Agent action selected",
      "tool.completed": "Safe action completed",
      "search.lead.discovered": "Candidate lead observed",
      "candidate_page.approval_required": "Collection approval required",
      "candidate_page.approved": "Candidate collection approved",
      "candidate_page.collected": "Candidate page collected",
      "assertion.proposed": "Review assertion proposed",
      "review.required": "Human review required",
      "run.completed": "Investigation completed",
    };
    if (!Object.hasOwn(labelByKind, event.kind)) return;
    timeline.push({
      sequence: event.sequence,
      label: labelByKind[event.kind],
      detail: event.payload?.url || event.payload?.label || formatTime(event.occurred_at),
      occurredAt: event.occurred_at,
      targetId: (details.graph?.animations || []).find((item) => item.sequence === event.sequence)?.target_id || null,
      event,
    });
  });
  return { nodes, edges, timeline, mode: "Live investigation replay" };
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
    "Public observations": { x: 210, y: -100 },
    "Pending leads": { x: 285, y: 115 },
    "Linked destinations": { x: 270, y: 70 },
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
  appendGraphFilters();
  renderAccessibleGraph();
  window.setTimeout(fitGraph, 80);
  window.setTimeout(fitGraph, 1100);
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
  const miniRect = refs.graphMinimap.getBoundingClientRect();
  refs.graphMinimap.width = Math.floor(miniRect.width * view.dpr);
  refs.graphMinimap.height = Math.floor(miniRect.height * view.dpr);
  miniCtx.setTransform(view.dpr, 0, 0, view.dpr, 0, 0);
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
  return item.sequence <= view.playbackCutoff && view.nodeFilters.has(item.presentation.visualKind);
}

function isEdgeVisible(edge) {
  const source = view.nodeById.get(edge.source);
  const target = view.nodeById.get(edge.target);
  return edge.sequence <= view.playbackCutoff && source && target && isVisible(source) && isVisible(target);
}

function appendGraphFilters() {
  document.querySelector("[data-graph-filter-section]")?.remove();
  const defaults = {
    page: { label: "Pages", color: "#ed1764", icon: "▤" },
    contact: { label: "Contacts", color: "#00b4a6", icon: "@" },
    brand: { label: "Brands", color: "#ff8a00", icon: "◇" },
    transaction: { label: "Transactions", color: "#ff8a00", icon: "$" },
    offer: { label: "Offers", color: "#f2c94c", icon: "%" },
    destination: { label: "Destinations", color: "#32b9e8", icon: "↗" },
    candidate: { label: "Candidates", color: "#8a5cf6", icon: "☆" },
    other: { label: "Other", color: "#8b95a7", icon: "···" },
  };
  const filterOrder = Object.keys(defaults);
  const counts = new Map(filterOrder.map((kind) => [kind, 0]));
  view.nodes.forEach((item) => counts.set(item.presentation.visualKind, (counts.get(item.presentation.visualKind) || 0) + 1));
  const list = el("div", "graph-filter-list");
  filterOrder.forEach((kind) => {
    const presentation = view.nodes.find((item) => item.presentation.visualKind === kind)?.presentation || defaults[kind];
    const label = el("label", "graph-filter");
    label.style.setProperty("--filter-color", presentation.color);
    const checkbox = el("input");
    checkbox.type = "checkbox";
    checkbox.checked = view.nodeFilters.has(kind);
    checkbox.addEventListener("change", () => {
      if (checkbox.checked) view.nodeFilters.add(kind);
      else view.nodeFilters.delete(kind);
      const visibleNodes = view.nodes.filter(isVisible);
      const visibleIds = new Set(visibleNodes.map((item) => item.id));
      const visibleEdges = view.edges.filter((edge) => visibleIds.has(edge.source) && visibleIds.has(edge.target));
      refs.graphCount.textContent = `${visibleNodes.length} visible · ${view.nodes.length} total · ${visibleEdges.length} links`;
      refs.graphEmpty.hidden = visibleNodes.length > 0;
    });
    label.append(
      checkbox,
      el("span", "graph-filter-icon", presentation.icon),
      el("span", "", presentation.label),
      el("span", "graph-filter-count", counts.get(kind) || 0),
    );
    list.append(label);
  });
  const section = intelSection("Graph filters", list);
  section.dataset.graphFilterSection = "true";
  refs.intelContent.append(section);
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
  view.edges.filter(isEdgeVisible).forEach((edge) => {
    const points = curvePoints(edge, time);
    if (!points) return;
    const age = reduceMotion ? 1 : Math.min(1, Math.max(0, (time - edge.birth) / 650));
    const selected = edge.source === view.selectedId || edge.target === view.selectedId;
    const searchDimmed = view.query && !view.searchIds.has(edge.source) && !view.searchIds.has(edge.target);
    ctx.save();
    ctx.globalAlpha = (searchDimmed ? 0.08 : selected ? 0.96 : 0.48) * age;
    const targetColor = view.nodeById.get(edge.target)?.presentation.color || "#32b9e8";
    ctx.strokeStyle = edge.appearance === "solid_emphasized" ? "#34d399" : edge.appearance === "dashed" ? "#8a5cf6" : targetColor;
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

function traceNodeShape(shape, radius) {
  ctx.beginPath();
  if (shape === "roundSquare") {
    ctx.roundRect(-radius, -radius, radius * 2, radius * 2, Math.max(5, radius * 0.32));
    return;
  }
  if (shape === "diamond") {
    ctx.moveTo(0, -radius * 1.12);
    ctx.lineTo(radius * 1.12, 0);
    ctx.lineTo(0, radius * 1.12);
    ctx.lineTo(-radius * 1.12, 0);
    ctx.closePath();
    return;
  }
  if (shape === "hex") {
    for (let index = 0; index < 6; index += 1) {
      const angle = Math.PI / 3 * index - Math.PI / 6;
      const x = Math.cos(angle) * radius;
      const y = Math.sin(angle) * radius;
      if (index === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    }
    ctx.closePath();
    return;
  }
  ctx.arc(0, 0, radius, 0, Math.PI * 2);
}

function drawNodes(time) {
  view.nodes.filter(isVisible).forEach((item) => {
    const point = worldToScreen(item, time);
    const age = reduceMotion ? 1 : Math.min(1, Math.max(0, (time - item.birth) / 420));
    const selected = item.id === view.selectedId;
    const hovered = item.id === view.hoverId;
    const searchDimmed = view.query && !view.searchIds.has(item.id);
    const color = item.presentation.color;
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
    traceNodeShape(item.presentation.shape, radius + 6 + pulse * 0.25);
    ctx.fill();
    ctx.stroke();
    ctx.setLineDash([]);
    ctx.fillStyle = "#0b141c";
    ctx.strokeStyle = `${color}aa`;
    ctx.lineWidth = 1;
    traceNodeShape(item.presentation.shape, radius);
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
    ctx.fillText(nodeCode(item), 0, 0);
    ctx.restore();
    if (!searchDimmed && (selected || hovered || item.primary || view.camera.zoom > 1.05)) roundedLabel(item.label, point.x, point.y + radius + 10, selected);
  });
}

function drawMinimap() {
  const width = refs.graphMinimap.clientWidth;
  const height = refs.graphMinimap.clientHeight;
  miniCtx.clearRect(0, 0, width, height);
  const visible = view.nodes.filter(isVisible);
  if (!visible.length) return;
  const bounds = graphBounds();
  const graphWidth = Math.max(160, bounds.maxX - bounds.minX + 80);
  const graphHeight = Math.max(120, bounds.maxY - bounds.minY + 80);
  const scale = Math.min((width - 18) / graphWidth, (height - 18) / graphHeight);
  const offsetX = (width - graphWidth * scale) / 2;
  const offsetY = (height - graphHeight * scale) / 2;
  const toMini = (item) => ({
    x: (item.x - bounds.minX + 40) * scale + offsetX,
    y: (item.y - bounds.minY + 40) * scale + offsetY,
  });
  miniCtx.save();
  miniCtx.globalAlpha = 0.42;
  view.edges.filter(isEdgeVisible).forEach((edge) => {
    const source = view.nodeById.get(edge.source);
    const target = view.nodeById.get(edge.target);
    if (!source || !target) return;
    const a = toMini(source);
    const b = toMini(target);
    miniCtx.strokeStyle = edge.appearance === "solid_emphasized" ? colors.public_contact : "#699bc0";
    miniCtx.lineWidth = 0.8;
    miniCtx.beginPath();
    miniCtx.moveTo(a.x, a.y);
    miniCtx.lineTo(b.x, b.y);
    miniCtx.stroke();
  });
  miniCtx.globalAlpha = 0.86;
  visible.forEach((item) => {
    const point = toMini(item);
    miniCtx.fillStyle = item.presentation.color;
    miniCtx.beginPath();
    miniCtx.arc(point.x, point.y, item.primary ? 3.2 : 2.1, 0, Math.PI * 2);
    miniCtx.fill();
  });
  const viewportWidth = view.width / view.camera.zoom;
  const viewportHeight = view.height / view.camera.zoom;
  const viewportX = (view.camera.x - viewportWidth / 2 - bounds.minX + 40) * scale + offsetX;
  const viewportY = (view.camera.y - viewportHeight / 2 - bounds.minY + 40) * scale + offsetY;
  miniCtx.globalAlpha = 0.72;
  miniCtx.strokeStyle = "#d9edf7";
  miniCtx.setLineDash([3, 3]);
  miniCtx.strokeRect(viewportX, viewportY, viewportWidth * scale, viewportHeight * scale);
  miniCtx.restore();
}

function paintFrame(time) {
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
  drawMinimap();
}

function drawFrame(time) {
  if (!document.hidden && !refs.workspaceView.hidden) paintFrame(time);
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
  view.selectedEvidenceId = null;
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

function timelinePresentation(item) {
  const kind = String(item.event?.kind || item.label || "").toLowerCase();
  if (kind.includes("blocked") || kind.includes("failed")) return { icon: "!", color: "#ff6577" };
  if (kind.includes("review") || kind.includes("assertion")) return { icon: "✓", color: "#34d399" };
  if (kind.includes("candidate") || kind.includes("lead")) return { icon: "☆", color: "#8a5cf6" };
  if (kind.includes("agent") || kind.includes("tool") || kind.includes("objective")) return { icon: "◇", color: "#32b9e8" };
  if (kind.includes("observation") || kind.includes("semantic") || kind.includes("extract")) return { icon: "◉", color: "#00b4a6" };
  if (kind.includes("capture") || kind.includes("page") || kind.includes("artifact") || kind.includes("crawl")) return { icon: "▤", color: "#ed1764" };
  if (kind.includes("completed") || kind.includes("adequate")) return { icon: "✓", color: "#34d399" };
  return { icon: "·", color: "#8b95a7" };
}

function renderTimeline() {
  refs.timelineTrack.replaceChildren();
  view.timeline.forEach((item, index) => {
    const card = el("button", "timeline-card");
    const presentation = timelinePresentation(item);
    card.type = "button";
    card.dataset.sequence = String(item.sequence);
    card.dataset.icon = presentation.icon;
    card.style.setProperty("--event-color", presentation.color);
    const timestamp = el("time", "", formatTime(item.occurredAt));
    timestamp.dateTime = item.occurredAt || "";
    timestamp.title = exactTime(item.occurredAt);
    card.append(el("b", "", item.label), el("span", "", item.detail), timestamp);
    card.addEventListener("click", () => {
      stopReplay();
      view.playbackCutoff = item.sequence;
      setActiveTimeline(index);
      const target = view.nodeById.get(item.targetId);
      if (target) selectNode(target, true);
      else if (view.currentKind === "run" && item.event) {
        renderRunEventInspector(view.currentDetails, item.event);
      }
    });
    refs.timelineTrack.append(card);
  });
  refs.timelineScrubber.min = "0";
  refs.timelineScrubber.max = String(Math.max(0, view.timeline.length - 1));
  refs.timelineScrubber.value = String(Math.max(0, view.timeline.length - 1));
  refs.timelineScrubber.disabled = !view.timeline.length;
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
  if (index >= 0 && view.timeline[index]) {
    refs.timelineScrubber.value = String(index);
    refs.timelineCurrentTime.textContent = formatTime(view.timeline[index].occurredAt);
    refs.timelineCurrentTime.title = exactTime(view.timeline[index].occurredAt);
    refs.timelineMode.textContent = index === view.timeline.length - 1 ? "REPLAY" : "CAPTURED";
  } else {
    refs.timelineCurrentTime.textContent = "Time not recorded";
    refs.timelineMode.textContent = "REPLAY";
  }
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

function indicatorSummaryFor(details) {
  return details?.gambling_indicators || details?.source_case?.gambling_indicators || {
    status: "insufficient_evidence",
    indicator_count: 0,
    reviewed_observation_count: 0,
    category_counts: {},
    osint_counts: {},
    classifications: [],
    limitations: [],
  };
}

function indicatorBoundary(summary) {
  const block = el("div", "indicator-boundary");
  block.append(
    el("strong", "", `${summary.indicator_count || 0} evidence item${summary.indicator_count === 1 ? "" : "s"}`),
    el("p", "", "Rule-classified public text/entity evidence. This count is not a percentage, probability, legal conclusion, or operator attribution."),
  );
  const categories = Object.entries(summary.category_counts || {});
  if (categories.length) {
    const tags = el("div", "indicator-tags");
    categories.forEach(([category, count]) => tags.append(el("span", "", `${titleCase(category)} · ${count}`)));
    block.append(tags);
  }
  return block;
}

function renderCaseIntel(details) {
  const host = hostnameFrom(details.final_url_display || details.seed_url_display);
  const hero = el("section", "intel-hero");
  hero.append(
    el("h1", "", host),
    el("p", "", `${details.pages?.length || 0} captured public page${details.pages?.length === 1 ? "" : "s"}. The canvas shows relationships; screenshots and source artifacts stay in the evidence inspector.`),
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
  const indicators = indicatorSummaryFor(details);
  stats.append(
    metricCard(details.pages?.length || 0, "Captured pages"),
    metricCard(details.evidence?.length || 0, "Verified artifacts"),
    metricCard(details.observations?.length || 0, "Semantic observations"),
    metricCard(details.candidates?.length || 0, "Pending leads"),
    metricCard(indicators.indicator_count || 0, "Judol indicators"),
  );

  const limitations = el("ul", "limitation-list");
  const limitValues = [...(details.limitation_reasons || [])];
  if (details.extraction_skip_reason) limitValues.push(details.extraction_skip_reason);
  if (!limitValues.length) limitValues.push("Public read-only collection; no authentication or access-control bypass.");
  limitValues.forEach((reason) => limitations.append(el("li", "", reason)));

  const policy = el("p", "policy-copy", "A candidate is a pending lead, never a confirmed operator or mirror. Similarity is evidence comparison, not ownership probability. Human review remains required.");
  refs.intelContent.replaceChildren(
    hero,
    intelSection("Capture facts", stats),
    intelSection("OSINT indicator boundary", indicatorBoundary(indicators)),
    intelSection("Known limits", limitations),
    intelSection("Interpretation boundary", policy),
  );
}

function renderRunIntel(details) {
  const source = details.source_case;
  const indicators = indicatorSummaryFor(details);
  const runNodes = details.graph?.nodes || [];
  const events = details.events || [];
  const capturedPages = source?.pages?.length
    || runNodes.filter((item) => ["seed_page", "collected_page"].includes(item.kind)).length;
  const semanticEvidence = Math.max(
    source?.observations?.length || 0,
    events.filter((item) => item.kind === "observation.created").length,
  );
  const completedActions = details.action_summary?.status === "completed"
    ? 1
    : events.filter((item) => item.kind === "tool.completed").length;
  const host = hostnameFrom(source?.final_url_display || source?.seed_url_display || details.case_id);
  const hero = el("section", "intel-hero");
  hero.append(
    el("h1", "", host),
    el("p", "", details.source_kind === "live_capture"
      ? `Live bounded investigation using ${details.agent_mode === "codex" ? valueOr(details.agent_model, "Codex") : "the deterministic safe fallback"}. Every graph transition replays an immutable local event.`
      : "Controlled evidence replay. Dashed edges are leads; emphasized assertion edges require a recorded human decision."),
  );
  const statuses = el("div", "status-row");
  statuses.append(
    statusPill(details.agent_mode || "deterministic fallback", details.agent_mode === "codex" ? "good" : "warn"),
    statusPill(details.capture_adequacy || source?.capture_adequacy || "controlled evidence", (details.capture_adequacy || source?.capture_adequacy) === "adequate" ? "good" : "warn"),
    statusPill(details.extraction_tier || source?.extraction_tier || "fixture", (details.extraction_tier || source?.extraction_tier) === "verified" ? "good" : "warn"),
    statusPill(details.lead_status || "recorded", details.lead_status === "recollected" ? "good" : "warn"),
  );
  hero.append(statuses);
  const stats = el("div", "stat-grid");
  stats.append(
    metricCard(capturedPages, "Captured pages"),
    metricCard(semanticEvidence, "Semantic evidence"),
    metricCard(details.pending_leads?.length || 0, "Approval leads"),
    metricCard(completedActions, "Safe agent actions"),
    metricCard(indicators.indicator_count || 0, "Judol indicators"),
  );
  const policy = el("p", "policy-copy", "Replay animation is a projection of persisted events. Reloading reconstructs the same graph truth; animation never creates evidence.");
  refs.intelContent.replaceChildren(
    hero,
    intelSection("Run facts", stats),
    intelSection("OSINT indicator boundary", indicatorBoundary(indicators)),
    intelSection("Evidence rule", policy),
  );
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
  const preferred = page?.full_page_screenshot_evidence_id || page?.screenshot_evidence_id || page?.initial_screenshot_evidence_id;
  return details.evidence?.find((item) => item.id === preferred)
    || details.evidence?.find((item) => String(item.type).includes("screenshot"))
    || null;
}

function screenshotsForCase(details, selected) {
  const pageFromNode = selected?.attributes?.page;
  const page = pageFromNode
    || details.pages?.find((item) => `page:${item.id}` === selected?.id)
    || details.pages?.[0];
  if (!page) return [];
  const labels = [
    [page.initial_screenshot_evidence_id, "Initial"],
    [page.screenshot_evidence_id, "Canonical"],
    [page.full_page_screenshot_evidence_id, "Full page"],
  ];
  const seen = new Set();
  return labels.flatMap(([id, label]) => {
    if (!id || seen.has(id)) return [];
    seen.add(id);
    const record = details.evidence?.find((item) => item.id === id);
    return record ? [{ record, label }] : [];
  });
}

function renderScreenshotGallery(details, selected) {
  const screenshots = screenshotsForCase(details, selected);
  if (!screenshots.length) return null;
  const defaultScreenshot = screenshots.find((item) => item.label === "Full page")
    || screenshots.find((item) => item.label === "Canonical")
    || screenshots[0];
  const defaultIndex = screenshots.indexOf(defaultScreenshot);
  const gallery = el("figure", "evidence-preview screenshot-gallery");
  const image = el("img");
  const label = el("figcaption", "preview-label", defaultScreenshot.label);
  const strip = el("div", "screenshot-strip");
  const show = (item, button) => {
    image.src = caseArtifactUrl(details.case_id, item.record.id);
    image.alt = `${item.label} screenshot evidence for ${hostnameFrom(details.final_url_display)}`;
    label.textContent = `${item.label} · ${item.record.image_dimensions?.width || "?"} × ${item.record.image_dimensions?.height || "?"}`;
    [...strip.children].forEach((child) => child.classList.toggle("active", child === button));
  };
  screenshots.forEach((item, index) => {
    const button = el("button", "screenshot-thumb", item.label);
    button.type = "button";
    button.addEventListener("click", () => show(item, button));
    strip.append(button);
    if (index === defaultIndex) window.queueMicrotask(() => show(item, button));
  });
  image.loading = "eager";
  gallery.append(image, label, strip);
  return gallery;
}

function observationPresentation(observation) {
  const type = String(observation?.type || observation?.observation_type || "");
  if (type.includes("whatsapp")) return { label: "WhatsApp identifier", icon: "WA", color: "#00b4a6" };
  if (type.includes("telegram")) return { label: "Telegram identifier", icon: "TG", color: "#00b4a6" };
  if (type.includes("email")) return { label: "Email address", icon: "@", color: "#00b4a6" };
  if (type.includes("phone")) return { label: "Phone number", icon: "TEL", color: "#00b4a6" };
  if (type === "claimed_brand_identity") return { label: "Claimed brand", icon: "◇", color: "#ff8a00" };
  if (type.includes("payment")) return { label: "Public payment observation", icon: "$", color: "#ff8a00" };
  if (type.includes("offer")) return { label: "Public offer claim", icon: "%", color: "#f2c94c" };
  if (type.includes("outgoing") || type.includes("redirect") || type.includes("download")) return { label: "Public destination", icon: "↗", color: "#32b9e8" };
  return { label: titleCase(type), icon: "···", color: "#8b95a7" };
}

function artifactPresentation(record) {
  const type = String(record?.type || record?.media_type || record?.name || "artifact").toLowerCase();
  if (type.includes("screenshot") || type.includes("png") || type.includes("image")) return { label: titleCase(record.type || "Screenshot"), icon: "IMG", color: "#ed1764" };
  if (type.includes("readiness") || type.includes("response") || type.includes("network")) return { label: titleCase(record.type || "Capture metadata"), icon: "META", color: "#32b9e8" };
  if (type.includes("html")) return { label: "Rendered HTML", icon: "HTML", color: "#8b95a7" };
  if (type.includes("text")) return { label: "Visible text", icon: "TXT", color: "#8b95a7" };
  return { label: titleCase(record.type || record.name || "Artifact"), icon: "DOC", color: "#8b95a7" };
}

function relatedNodeIdForObservation(observationId, sourcePageId) {
  const direct = view.nodes.find((node) => (
    node.attributes?.observation_id === observationId
    || node.attributes?.observation?.id === observationId
    || (node.attributes?.observations || []).some((item) => item.id === observationId)
  ));
  if (direct) return direct.id;
  return view.nodes.find((node) => node.id === `page:${sourcePageId}` || node.attributes?.page?.id === sourcePageId)?.id || null;
}

function buildCaseEvidenceCards(details) {
  const cards = [];
  const evidenceById = new Map((details.evidence || []).map((item) => [item.id, item]));
  const indicatorsByObservation = new Map((details.gambling_indicators?.classifications || []).map((item) => [item.observation_id, item]));
  (details.evidence || []).forEach((record) => {
    const presentation = artifactPresentation(record);
    const pageNode = view.nodes.find((node) => node.id === `page:${record.page_id}` || node.attributes?.page?.id === record.page_id);
    cards.push({
      id: `artifact:${record.id}`,
      title: presentation.label,
      value: record.id,
      icon: presentation.icon,
      color: presentation.color,
      occurredAt: record.collected_at,
      nodeId: pageNode?.id || null,
      previewUrl: String(record.type).includes("screenshot") ? caseArtifactUrl(details.case_id, record.id) : null,
      facts: [
        ["Artifact ID", record.id],
        ["Source page", record.page_id],
        ["Collected", exactTime(record.collected_at)],
        ["SHA-256", record.sha256],
        ["Dimensions", record.image_dimensions ? `${record.image_dimensions.width} × ${record.image_dimensions.height}` : null],
        ["Integrity", record.artifact_available ? "Verified and available" : "Unavailable"],
      ],
    });
  });
  (details.observations || []).forEach((observation) => {
    const presentation = observationPresentation(observation);
    const indicator = indicatorsByObservation.get(observation.id);
    const sourceArtifact = evidenceById.get(observation.source_artifact_id);
    const screenshotId = observation.crop_evidence_id || observation.screenshot_evidence_id;
    cards.push({
      id: `observation:${observation.id}`,
      title: presentation.label,
      value: observation.display_value,
      icon: presentation.icon,
      color: presentation.color,
      occurredAt: sourceArtifact?.collected_at,
      nodeId: relatedNodeIdForObservation(observation.id, observation.source_page_id),
      previewUrl: screenshotId ? caseArtifactUrl(details.case_id, screenshotId) : null,
      facts: [
        ["Observation ID", observation.id],
        ["Raw / displayed", observation.display_value],
        ["Source page", observation.source_page_id],
        ["Source artifact", observation.source_artifact_id],
        ["Screenshot / crop", screenshotId],
        ["Extraction", observation.extraction_method],
        ["Context", observation.surrounding_text],
        ["Indicator", indicator?.label === "indicator" ? `${titleCase(indicator.category)} · ${(indicator.matched_terms || []).join(", ")}` : "Not counted by the controlled indicator policy"],
        ["Limitations", (observation.limitations || []).join(" · ") || "None recorded"],
      ],
    });
  });
  (details.candidates || []).forEach((candidate, index) => {
    const candidateNode = view.nodes.find((node) => node.label === candidate.hostname || node.attributes?.url === candidate.url);
    cards.push({
      id: `candidate:${candidate.id || candidate.hostname || index}`,
      title: "Pending candidate lead",
      value: candidate.hostname || candidate.url,
      icon: "☆",
      color: "#8a5cf6",
      occurredAt: null,
      nodeId: candidateNode?.id || null,
      facts: [
        ["Status", "Relationship not determined"],
        ["Candidate", candidate.hostname || candidate.url],
        ["Policy", details.candidate_policy_version],
        ["Reasons", (candidate.reasons || []).map((reason) => reason.code || reason.type || reason.reason).filter(Boolean).join(" · ") || "Evidence-backed candidate rule"],
        ["Limitation", "A candidate is not a confirmed mirror, operator, or ownership conclusion."],
      ],
    });
  });
  return cards;
}

function buildRunEvidenceCards(details) {
  const cards = details.source_case ? buildCaseEvidenceCards(details.source_case) : [];
  (details.artifacts || []).forEach((artifact) => {
    const presentation = artifactPresentation(artifact);
    cards.push({
      id: `run-artifact:${artifact.name}`,
      title: presentation.label,
      value: artifact.name,
      icon: presentation.icon,
      color: presentation.color,
      occurredAt: null,
      nodeId: null,
      previewUrl: String(artifact.media_type).includes("image") ? runArtifactUrl(details.workspace_id, artifact.name) : null,
      facts: [["Artifact", artifact.name], ["Media type", artifact.media_type], ["Bytes", artifact.bytes], ["Scope", "Persisted run artifact"]],
    });
  });
  (details.pending_leads || []).forEach((lead) => {
    const node = view.nodes.find((item) => item.attributes?.lead_id === lead.lead_id || item.label === lead.url || item.label === hostnameFrom(lead.url));
    cards.push({
      id: `lead:${lead.lead_id}`,
      title: "Candidate lead",
      value: lead.url,
      icon: "☆",
      color: "#8a5cf6",
      occurredAt: lead.created_at,
      nodeId: node?.id || null,
      facts: [["Lead ID", lead.lead_id], ["Discovery", titleCase(lead.discovery_method)], ["Collection", titleCase(lead.initial_status)], ["Source observations", (lead.source_observation_ids || []).join(", ")], ["Limitation", "Candidate relationship requires collection and human review."]],
    });
  });
  const assertions = new Map((details.assertions || []).map((item) => [item.assertion_id, item]));
  if (details.assertion) assertions.set(details.assertion.assertion_id, details.assertion);
  assertions.forEach((assertion) => {
    const edge = view.edges.find((item) => item.id === `assertion:${assertion.assertion_id}`);
    cards.push({
      id: `assertion:${assertion.assertion_id}`,
      title: "Candidate assertion",
      value: `${assertion.subject} → ${assertion.object}`,
      icon: "◇",
      color: "#8a5cf6",
      occurredAt: assertion.created_at,
      nodeId: edge?.target || null,
      facts: [["Assertion ID", assertion.assertion_id], ["Relation", titleCase(assertion.assertion_type)], ["Review", titleCase(details.assertion_statuses?.[assertion.assertion_id] || details.current_assertion_status || "needs review")], ["Observations", (assertion.supporting_observation_ids || []).join(", ")], ["Artifacts", (assertion.source_artifact_ids || []).join(", ")], ["Limitations", (assertion.limitations || []).join(" · ")]],
    });
  });
  (details.all_reviews || details.reviews || []).forEach((review) => {
    cards.push({
      id: `review:${review.review_id}`,
      title: "Human review decision",
      value: titleCase(review.outcome),
      icon: "✓",
      color: review.outcome === "verified" ? "#34d399" : review.outcome === "rejected" ? "#ff6577" : "#f2c94c",
      occurredAt: review.occurred_at,
      nodeId: view.edges.find((item) => item.id === `assertion:${review.assertion_id}`)?.target || null,
      facts: [["Review ID", review.review_id], ["Assertion", review.assertion_id], ["Reviewer label", review.reviewer_label], ["Outcome", titleCase(review.outcome)], ["Reason", review.reason], ["Version", `${review.previous_version} → ${review.new_version}`]],
    });
  });
  return cards;
}

function renderEvidenceCatalog(cards, selected) {
  const catalog = el("div", "evidence-catalog");
  const matchedCard = cards.find((card) => card.nodeId && card.nodeId === selected?.id);
  const activeId = view.selectedEvidenceId || matchedCard?.id || null;
  cards.forEach((card) => {
    const button = el("button", `evidence-card${card.id === activeId ? " selected" : ""}`);
    button.type = "button";
    button.style.setProperty("--card-color", card.color);
    button.setAttribute("aria-expanded", card.id === activeId ? "true" : "false");
    const copy = el("span", "evidence-card-copy");
    copy.append(el("b", "", card.title), el("strong", "", card.value), el("small", "", card.facts.find((fact) => fact[1])?.[1] || "Evidence-backed record"));
    const timestamp = el("time", "", formatTime(card.occurredAt));
    timestamp.title = exactTime(card.occurredAt);
    const detail = el("span", "evidence-card-detail");
    if (card.previewUrl) {
      const image = el("img");
      image.src = card.previewUrl;
      image.alt = `${card.title} supporting screenshot`;
      image.loading = "lazy";
      detail.append(image);
    }
    detail.append(factList(card.facts));
    button.append(el("span", "evidence-card-icon", card.icon), copy, timestamp, detail);
    button.addEventListener("click", () => {
      view.selectedEvidenceId = card.id === view.selectedEvidenceId ? null : card.id;
      const node = card.nodeId ? view.nodeById.get(card.nodeId) : null;
      if (node) {
        view.selectedId = node.id;
        focusNode(node);
      }
      if (view.currentKind === "case") renderCaseInspector(view.currentDetails, node || selected);
      else renderRunInspector(view.currentDetails, node || selected);
    });
    catalog.append(button);
  });
  if (!cards.length) catalog.append(el("p", "policy-copy", "No evidence records are available for this verified package."));
  return catalog;
}

function selectedNodeFacts(details, selected) {
  const presentation = selected?.presentation || presentationFor(selected?.kind || "other");
  const attributes = selected?.attributes || {};
  const observation = attributes.observation || details?.source_case?.observations?.find((item) => item.id === attributes.observation_id);
  const page = attributes.page || details?.pages?.find((item) => `page:${item.id}` === selected?.id) || details?.source_case?.pages?.find((item) => `page:${item.id}` === selected?.id);
  if (presentation.visualKind === "page") return factList([
    ["Type", presentation.label], ["URL", selected?.label], ["Node state", titleCase(selected?.status)],
    ["Access", page?.access_outcome], ["Capture quality", page?.capture_adequacy], ["Extraction", page?.extraction_tier],
    ["Limitations", (page?.limitation_reasons || []).join(" · ") || "None recorded"],
  ]);
  if (presentation.visualKind === "contact" || presentation.visualKind === "brand") return factList([
    ["Type", presentation.label], ["Observed value", observation?.display_value || selected?.label], ["Raw value", observation?.raw_value],
    ["Source page", observation?.source_page_id || attributes.source_node_id], ["Source artifact", observation?.source_artifact_id || attributes.source_artifact_id],
    ["Extraction", observation?.extraction_method], ["Context", observation?.surrounding_text], ["Review", "Observation only · no ownership attribution"],
  ]);
  if (["transaction", "offer", "other"].includes(presentation.visualKind)) return factList([
    ["Type", presentation.label], ["Category", attributes.claim_category], ["Values", (attributes.values || [selected?.label]).join(" · ")],
    ["Observations", attributes.observation_count || attributes.observations?.length], ["State", titleCase(selected?.status)], ["Meaning", "Publicly displayed claim; not a legal or ownership conclusion"],
  ]);
  if (["destination", "candidate"].includes(presentation.visualKind)) return factList([
    ["Type", presentation.label], ["Destination", attributes.url || selected?.label], ["State", titleCase(selected?.status)],
    ["Relationship", attributes.relationship || "Candidate relationship not determined"], ["Matched case", attributes.matched_case_id], ["Review", "Human review required for candidate relation"],
  ]);
  return factList([["Type", presentation.label], ["State", titleCase(selected?.status)], ["Node ID", selected?.id], ["Label", selected?.label]]);
}

function renderLegacyCaseInspector(details, selected) {
  const screenshot = findScreenshot(details, selected);
  const selectedEvidence = selected?.attributes?.evidence;
  const header = inspectorHeader(
    selected ? titleCase(selected.kind) : "Capture evidence",
    selected?.label || hostnameFrom(details.final_url_display),
    selected?.kind === "candidate_domain" ? evidenceSemantics.candidate : "Evidence shown here is loaded from the verified local case manifest.",
  );
  const children = [header];
  const gallery = renderScreenshotGallery(details, selected);
  if (gallery) children.push(gallery);

  const facts = factList([
    ["Public state", titleCase(details.public_status)],
    ["Adequacy", titleCase(details.capture_adequacy || "legacy capture")],
    ["Access", titleCase(details.access_outcome || details.capture_outcome)],
    ["Extraction", details.extraction_eligible ? titleCase(details.extraction_tier || "eligible") : `Withheld · ${valueOr(details.extraction_skip_reason, "capture limit")}`],
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
        el("span", "", `${titleCase(observation.evidence_strength)} evidence · ${valueOr(observation.extraction_method, "recorded extractor")}`),
      );
      observations.append(card);
    });
  } else {
    observations.append(el("p", "policy-copy", "Extraction withheld or no semantic observation recorded. This is not an absence claim."));
  }
  children.push(evidenceBlock("Semantic evidence", observations));

  const indicatorSummary = indicatorSummaryFor(details);
  const indicatorEvidence = el("div");
  const counted = (indicatorSummary.classifications || []).filter((item) => item.label === "indicator");
  counted.forEach((item) => {
    const card = el("article", "observation-card indicator-card");
    card.append(
      el("b", "", titleCase(item.category)),
      el("strong", "", item.display_value || item.observation_id),
      el("span", "", `${item.observation_id} · ${item.matched_terms?.join(", ") || "page context"}`),
      el("span", "", `Source ${item.source_artifact_id} · screenshot ${item.screenshot_evidence_id}`),
    );
    indicatorEvidence.append(card);
  });
  if (!counted.length) indicatorEvidence.append(el("p", "policy-copy", "No controlled judol indicator matched this captured evidence. This is not an absence claim."));
  children.push(evidenceBlock(
    `Judol indicators · ${indicatorSummary.indicator_count || 0}`,
    indicatorEvidence,
  ));

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

function renderCaseInspector(details, selected) {
  const presentation = selected?.presentation || presentationFor(selected?.kind || "other");
  const header = inspectorHeader(
    presentation.label,
    selected?.label || hostnameFrom(details.final_url_display),
    selected?.status === "lead" ? evidenceSemantics.candidate : "Every displayed fact below resolves to a verified local artifact or deterministic observation.",
  );
  const children = [header];
  const gallery = renderScreenshotGallery(details, selected);
  if (gallery) children.push(gallery);
  children.push(evidenceBlock("Selected node", selectedNodeFacts(details, selected)));
  const cards = buildCaseEvidenceCards(details);
  children.push(evidenceBlock(`Evidence catalog · ${cards.length}`, renderEvidenceCatalog(cards, selected)));
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

function renderLegacyRunInspector(details, selected) {
  const header = inspectorHeader(
    selected ? titleCase(selected.kind) : "Investigation node",
    selected?.label || details.case_id,
    selected?.status === "lead" ? evidenceSemantics.candidate : "This node is reconstructed from the append-only event stream.",
  );
  const attributes = selected?.attributes || {};
  const facts = factList([
    ["Node state", titleCase(selected?.status)],
    ["Agent", details.agent_mode === "codex" ? valueOr(details.agent_model, "Codex") : titleCase(details.agent_mode)],
    ["Evidence", titleCase(details.extraction_tier || details.source_case?.extraction_tier)],
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
  const children = [header];
  const interactionScreenshot = selected?.attributes?.screenshot_artifact;
  if (interactionScreenshot) {
    const figure = el("figure", "evidence-preview");
    const image = el("img");
    image.src = runArtifactUrl(details.workspace_id, interactionScreenshot);
    image.alt = `Interaction screenshot evidence for ${selected.label}`;
    image.loading = "eager";
    figure.append(image, el("figcaption", "preview-label", "Post-action screenshot evidence"));
    children.push(figure);
  } else if (details.source_case) {
    const gallery = renderScreenshotGallery(details.source_case, selected);
    if (gallery) children.push(gallery);
  }
  children.push(evidenceBlock("Persisted state", facts));
  const indicators = indicatorSummaryFor(details);
  children.push(evidenceBlock(
    `Judol indicators · ${indicators.indicator_count || 0}`,
    summaryRows(
      (indicators.classifications || [])
        .filter((item) => item.label === "indicator")
        .map((item) => [item.display_value || item.observation_id, titleCase(item.category)]),
      "No controlled judol indicator matched the captured source evidence.",
    ),
  ));
  if (Object.keys(attributes).length) children.push(evidenceBlock("Node evidence", factList(Object.entries(attributes).slice(0, 8))));
  children.push(evidenceBlock("Run artifacts", artifactGrid));

  if (details.lead_status === "waiting_for_approval") {
    const approve = el("button", "", "Approve candidate collection");
    approve.type = "button";
    approve.className = "artifact-link";
    approve.addEventListener("click", async () => {
      approve.disabled = true;
      approve.textContent = "Collecting approved public page…";
      try {
        await postJson(`/api/mvp/runs/${encodeURIComponent(details.workspace_id)}/approve`, {});
        await loadRun(details.workspace_id);
        toast("Approval recorded before bounded candidate collection.", "success");
      } catch (error) {
        toast(error.message, "error");
        approve.disabled = false;
        approve.textContent = "Approve candidate collection";
      }
    });
    children.push(evidenceBlock("Approval boundary", approve));
  }
  if (details.assertion) children.push(evidenceBlock("Append human review", renderReviewForm(details)));
  refs.inspectorContent.replaceChildren(...children);
}

function renderRunInspector(details, selected) {
  const presentation = selected?.presentation || presentationFor(selected?.kind || "other");
  const header = inspectorHeader(
    presentation.label,
    selected?.label || details.case_id,
    selected?.status === "lead" ? evidenceSemantics.candidate : "This view is reconstructed from persisted events, evidence, assertions, and append-only review history.",
  );
  const children = [header];
  const interactionScreenshot = selected?.attributes?.screenshot_artifact;
  if (interactionScreenshot) {
    const figure = el("figure", "evidence-preview");
    const image = el("img");
    image.src = runArtifactUrl(details.workspace_id, interactionScreenshot);
    image.alt = `Interaction screenshot evidence for ${selected.label}`;
    image.loading = "eager";
    figure.append(image, el("figcaption", "preview-label", "Post-action screenshot evidence"));
    children.push(figure);
  } else if (details.source_case) {
    const gallery = renderScreenshotGallery(details.source_case, selected);
    if (gallery) children.push(gallery);
  }
  children.push(evidenceBlock("Selected node", selectedNodeFacts(details, selected)));
  const cards = buildRunEvidenceCards(details);
  children.push(evidenceBlock(`Evidence and claims · ${cards.length}`, renderEvidenceCatalog(cards, selected)));
  if (details.lead_status === "waiting_for_approval") {
    const approve = el("button", "artifact-link", "Approve candidate collection");
    approve.type = "button";
    approve.addEventListener("click", async () => {
      approve.disabled = true;
      approve.textContent = "Collecting approved public page…";
      try {
        await postJson(`/api/mvp/runs/${encodeURIComponent(details.workspace_id)}/approve`, {});
        await loadRun(details.workspace_id);
        toast("Approval recorded before bounded candidate collection.", "success");
      } catch (error) {
        toast(error.message, "error");
        approve.disabled = false;
        approve.textContent = "Approve candidate collection";
      }
    });
    children.push(evidenceBlock("Approval boundary", approve));
  }
  if (details.assertion) children.push(evidenceBlock("Append human review", renderReviewForm(details)));
  refs.inspectorContent.replaceChildren(...children);
}

function eventValue(value) {
  if (value === null || value === undefined) return "Not recorded";
  if (typeof value === "object") return shortText(JSON.stringify(value), 180);
  return String(value);
}

function renderRunEventInspector(details, event) {
  const payload = event.payload || {};
  const payloadEntries = [
    "status",
    "reason",
    "tool_name",
    "element_id",
    "policy_preflight",
    "executed",
    "outcome_summary",
    "artifact_id",
    "observation_id",
    "lead_id",
    "assertion_id",
    "lead_status",
  ]
    .filter((key) => Object.hasOwn(payload, key))
    .map((key) => [key, eventValue(payload[key])]);
  const header = inspectorHeader(
    "Persisted event",
    titleCase(event.kind.replaceAll(".", " ")),
    "This timeline entry is an immutable event projection; it does not execute an action when inspected.",
  );
  const envelope = factList([
    ["Sequence", event.sequence],
    ["Occurred", formatTime(event.occurred_at)],
    ["Event ID", event.event_id],
    ["Causation", event.causation_event_id],
    ["Schema", event.schema_version],
  ]);
  const children = [header, evidenceBlock("Event envelope", envelope)];
  if (payloadEntries.length) children.push(evidenceBlock("Bounded payload", factList(payloadEntries)));
  const artifacts = el("div", "artifact-grid");
  (details.artifacts || []).forEach((artifact) => {
    const link = el("a", "artifact-link", `${artifact.name} · ${artifact.bytes} B`);
    link.href = runArtifactUrl(details.workspace_id, artifact.name);
    artifacts.append(link);
  });
  children.push(evidenceBlock("Run artifacts", artifacts));
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
    refs.workspaceTitle.textContent = hostnameFrom(details.final_url_display || details.seed_url_display);
    refs.workspaceUrl.textContent = details.final_url_display || details.seed_url_display || "Saved capture";
    showScreen("workspace");
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
    refs.workspaceTitle.textContent = hostnameFrom(details.seed_url || details.case_id);
    refs.workspaceUrl.textContent = details.seed_url || details.case_id || "Saved investigation";
    showScreen("workspace");
    setStatus(`${details.case_id} · ${details.events?.length || 0} persisted events · ${titleCase(details.lead_status)}`);
  } catch (error) {
    renderError(error.message);
  }
}

function renderLegacyRecentCases() {
  refs.recentCases.replaceChildren();
  const recent = [
    ...view.runs.map((item) => ({
      kind: "run",
      id: item.workspace_id,
      title: hostnameFrom(item.seed_url || item.case_id),
      subtitle: item.case_id,
      state: titleCase(item.lead_status || item.agent_stop_reason || "captured"),
      updated: item.updated_at,
      indicators: item.gambling_indicator_count,
    })),
    ...view.cases.filter((item) => item.integrity === "verified").map((item) => ({
      kind: "case",
      id: item.case_id,
      title: hostnameFrom(item.final_url_display || item.seed_url_display),
      subtitle: item.case_id,
      state: titleCase(item.capture_adequacy || "verified"),
      updated: item.completed_at,
      indicators: item.gambling_indicator_count,
    })),
  ].slice(0, 6);
  if (!recent.length) {
    refs.recentCases.append(el("p", "quiet-copy", "No verified local cases yet."));
    return;
  }
  recent.forEach((item) => {
    const button = el("button", "recent-case");
    button.type = "button";
    const identity = el("span");
    identity.append(
      el("strong", "", item.title),
      el("small", "", `${item.subtitle}${Number.isInteger(item.indicators) ? ` · ${item.indicators} judol indicator${item.indicators === 1 ? "" : "s"}` : ""}`),
    );
    button.append(
      identity,
      el("span", "case-state", item.state),
      el("span", "open-label", item.updated ? formatTime(item.updated) : "Open →"),
    );
    button.addEventListener("click", () => {
      if (item.kind === "run") void loadRun(item.id);
      else void loadCase(item.id);
    });
    refs.recentCases.append(button);
  });
}

function caseCardState(item) {
  if (item.integrity === "error") return { key: "error", label: "Integrity error", tone: "bad" };
  const state = String(item.leadStatus || item.captureState || "complete");
  if (["waiting_for_approval", "needs_review", "review_required"].includes(state)) return { key: "review", label: "Needs review", tone: "warn" };
  if (["queued", "running"].includes(state)) return { key: "active", label: titleCase(state), tone: "" };
  if (state === "recollected") return { key: "complete", label: "Recollected", tone: "" };
  if (state === "limited") return { key: "complete", label: "Captured · limited", tone: "warn" };
  return { key: "complete", label: "Complete", tone: "" };
}

function renderRecentCases() {
  refs.recentCases.replaceChildren();
  refs.recentCases.classList.toggle("list-view", view.caseLayout === "list");
  const casesById = new Map(view.cases.map((item) => [item.case_id, item]));
  const representedCases = new Set(view.runs.map((item) => item.source_case_id).filter(Boolean));
  const entries = [
    ...view.runs.map((run) => {
      const source = casesById.get(run.source_case_id) || {};
      return {
        kind: "run",
        id: run.workspace_id,
        title: hostnameFrom(run.seed_url || source.final_url_display || run.case_id),
        caseId: run.case_id,
        updated: run.updated_at,
        pages: source.page_count || 0,
        indicators: source.gambling_indicator_count || 0,
        candidates: source.candidate_count || 0,
        leadStatus: run.lead_status,
        integrity: source.integrity || "verified",
      };
    }),
    ...view.cases.filter((item) => !representedCases.has(item.case_id)).map((item) => ({
      kind: "case",
      id: item.case_id,
      title: item.integrity === "verified" ? hostnameFrom(item.final_url_display || item.seed_url_display) : "Unverified case package",
      caseId: item.case_id,
      updated: item.completed_at || item.started_at,
      pages: item.page_count || 0,
      indicators: item.gambling_indicator_count || 0,
      candidates: item.candidate_count || 0,
      captureState: item.capture_adequacy,
      integrity: item.integrity,
      error: item.error,
    })),
  ];
  const query = view.caseQuery.toLowerCase();
  const filtered = entries.filter((item) => {
    const state = caseCardState(item);
    const filterMatches = view.caseFilter === "all" || state.key === view.caseFilter;
    const queryMatches = !query || `${item.title} ${item.caseId} ${state.label}`.toLowerCase().includes(query);
    return filterMatches && queryMatches;
  });
  filtered.sort((left, right) => {
    if (refs.caseSort.value === "name") return left.title.localeCompare(right.title);
    const delta = new Date(left.updated || 0).getTime() - new Date(right.updated || 0).getTime();
    return refs.caseSort.value === "oldest" ? delta : -delta;
  });
  if (!filtered.length) {
    refs.recentCases.append(el("p", "quiet-copy", entries.length ? "No cases match this view." : "No saved investigations yet."));
    return;
  }
  filtered.forEach((item) => {
    const state = caseCardState(item);
    const button = el("button", `recent-case${item.integrity === "error" ? " error" : ""}`);
    button.type = "button";
    button.disabled = item.integrity === "error";
    const head = el("span", "case-card-head");
    const identity = el("span");
    identity.append(el("strong", "", item.title), el("small", "", item.caseId));
    head.append(identity, el("span", `case-state ${state.tone}`.trim(), state.label));
    const metrics = el("span", "case-card-metrics");
    [[item.pages, "Pages"], [item.indicators, "Indicators"], [item.candidates, "Candidates"]].forEach(([value, label]) => {
      const metric = el("span");
      metric.append(el("b", "", value), document.createTextNode(label));
      metrics.append(metric);
    });
    const date = el("span");
    date.append(el("b", "", formatTime(item.updated)), document.createTextNode(item.error || "Updated WIB"));
    metrics.append(date, el("span", "case-card-arrow", item.integrity === "error" ? "!" : "→"));
    button.append(head, metrics);
    button.addEventListener("click", () => {
      if (item.kind === "run") void loadRun(item.id);
      else void loadCase(item.id);
    });
    refs.recentCases.append(button);
  });
}

function summaryCard(title, detail, content) {
  const card = el("section", "summary-card");
  const header = el("header");
  header.append(el("h2", "", title), el("small", "", detail));
  card.append(header, content);
  return card;
}

function summaryRows(items, emptyText = "Nothing recorded.") {
  const list = el("div", "summary-list");
  if (!items.length) {
    list.append(el("p", "quiet-copy", emptyText));
    return list;
  }
  items.forEach((item) => {
    const row = el("div", "summary-row");
    row.append(el("span", "", item[0]), el("span", "", item[1]));
    list.append(row);
  });
  return list;
}

function renderSummary() {
  const details = view.currentDetails;
  if (!details) return;
  const isRun = view.currentKind === "run";
  const sourceCase = isRun ? details.source_case || {} : details;
  const pages = sourceCase.pages || [];
  const observations = sourceCase.observations || [];
  const events = details.events || [];
  const artifacts = isRun ? details.artifacts || [] : details.evidence || [];
  const assertions = details.assertions || (details.assertion ? [details.assertion] : []);
  const pendingLeads = details.pending_leads || [];
  const pending = Number(details.pending_review_count || 0) + pendingLeads.length;
  const candidateCount = assertions.length + pendingLeads.length;
  const indicators = indicatorSummaryFor(details);
  const host = hostnameFrom(details.seed_url || sourceCase.final_url_display || sourceCase.seed_url_display || details.case_id);
  refs.summarySubtitle.textContent = `${host} · replay is reconstructed from persisted evidence and events.`;

  const stats = el("div", "summary-stat-grid");
  [
    [pages.length || details.pages_captured || 0, "Pages captured"],
    [observations.length || events.filter((item) => item.kind === "observation.created").length, "Public observations"],
    [candidateCount, "Candidate relations"],
    [pending, "Pending review"],
    [indicators.indicator_count || 0, "Judol indicators"],
  ].forEach(([value, label]) => {
    const stat = el("div", "summary-stat");
    stat.append(el("strong", "", value), el("span", "", label));
    stats.append(stat);
  });

  const left = el("div", "summary-column");
  left.append(summaryCard("Investigation at a glance", valueOr(details.case_id), stats));
  const scopeRows = [
    ["Seed", details.seed_url || sourceCase.seed_url_display || "Not recorded"],
    ["Collection", isRun ? titleCase(details.source_kind || "event sourced") : "Deterministic capture"],
    ["Agent stop", titleCase(details.agent_stop_reason || "not applicable")],
    ["Safety", "Public, read-only, policy gated"],
    ["Inference", "Candidates require human review"],
  ];
  left.append(summaryCard("Scope and limitations", "truthful operating envelope", summaryRows(scopeRows)));
  left.append(summaryCard(
    "Collected pages",
    `${pages.length} saved page records`,
    summaryRows(pages.map((page) => [page.final_url_display || page.final_url || page.normalized_url || page.url || page.id, titleCase(page.capture_adequacy || page.state || "captured")]), "No collected page list is attached to this run."),
  ));
  left.append(summaryCard(
    "Public OSINT evidence profile",
    `${indicators.reviewed_observation_count || 0} observation-level classifications`,
    summaryRows(
      Object.entries(indicators.osint_counts || {}).map(([category, count]) => [titleCase(category), `${count} evidence item${count === 1 ? "" : "s"}`]),
      "No semantic OSINT observations were available for classification.",
    ),
  ));
  left.append(summaryCard(
    "Judol indicator evidence",
    `${indicators.indicator_count || 0} counted · no percentage or probability`,
    summaryRows(
      (indicators.classifications || [])
        .filter((item) => item.label === "indicator")
        .map((item) => [
          `${item.display_value || item.observation_id} · ${item.observation_id}`,
          `${titleCase(item.category)} · ${item.matched_terms?.join(", ") || "context"}`,
        ]),
      "No controlled judol indicator matched the captured public evidence.",
    ),
  ));
  left.append(summaryCard(
    "Candidate relationships",
    `${assertions.length} assertions · ${pendingLeads.length} approval leads`,
    summaryRows([
      ...assertions.map((item) => [`${item.subject || item.subject_node_id || "subject"} → ${item.object || item.object_node_id || "candidate"}`, titleCase(item.assertion_type || item.relation || item.predicate || "candidate")]),
      ...pendingLeads.map((item) => [item.url || item.lead_id, "Waiting For Approval"]),
    ], "No candidate relationship or lead was observed."),
  ));

  const right = el("div", "summary-column");
  const exports = el("div", "export-grid");
  if (isRun) {
    [["Export Markdown", "md"], ["Export JSON", "json"], ["Export case archive", "zip"]].forEach(([label, extension]) => {
      const link = el("a", "", label);
      link.href = `/api/mvp/runs/${encodeURIComponent(details.workspace_id)}/export.${extension}`;
      link.download = `${details.case_id || "hawkeye-case"}.${extension}`;
      exports.append(link);
    });
  }
  const print = el("button", "", "Print summary");
  print.type = "button";
  print.addEventListener("click", () => window.print());
  exports.append(print);
  right.append(summaryCard("Export and print", "human and machine-readable", exports));

  const chronology = el("div", "chronology");
  events.slice(0, 80).forEach((event) => {
    const item = el("div", "chronology-item");
    const time = el("time", "", formatTime(event.occurred_at || event.created_at));
    const description = el("div");
    description.append(el("strong", "", titleCase(event.kind)), el("small", "", event.event_id || "persisted event"));
    item.append(time, description);
    chronology.append(item);
  });
  if (!events.length) chronology.append(el("p", "quiet-copy", "This deterministic case predates the append-only event runtime."));
  right.append(summaryCard("Event chronology", `${events.length} persisted events`, chronology));
  right.append(summaryCard(
    "Artifact manifest",
    `${artifacts.length} integrity-tracked files`,
    summaryRows(artifacts.map((item) => [item.name || item.path || item.id, `${item.bytes || item.type || "saved"}`]), "No artifact manifest is attached."),
  ));
  refs.summaryContent.replaceChildren(left, right);
}

function renderInspectorTab(tab) {
  refs.inspectorTabs.forEach((button) => {
    const active = button.dataset.inspectorTab === tab;
    button.classList.toggle("active", active);
    if (active) button.setAttribute("aria-current", "page");
    else button.removeAttribute("aria-current");
  });
  const details = view.currentDetails;
  if (!details || tab === "evidence") {
    selectNode(view.nodeById.get(view.selectedId));
    return;
  }
  if (tab === "overview") {
    const indicators = indicatorSummaryFor(details);
    refs.inspectorContent.replaceChildren(
      inspectorHeader("Investigation overview", hostnameFrom(details.seed_url || details.final_url_display || details.case_id), "A concise view of scope, state, and review posture."),
      evidenceBlock("Status", factList([
        ["Case", details.case_id],
        ["Lead state", details.lead_status || "Not applicable"],
        ["Agent stop", details.agent_stop_reason || "Not applicable"],
        ["Events", details.events?.length || 0],
        ["Judol indicators", indicators.indicator_count || 0],
        ["Indicator policy", indicators.policy_version || "evidence-count-v1"],
      ])),
      evidenceBlock("Interpretation", indicatorBoundary(indicators)),
    );
    return;
  }
  if (tab === "artifacts") {
    const grid = el("div", "artifact-grid");
    (details.artifacts || details.evidence || []).forEach((artifact) => {
      const link = el("a", "artifact-link", artifact.name || artifact.path || artifact.id);
      if (view.currentKind === "run") link.href = runArtifactUrl(details.workspace_id, artifact.name);
      else link.href = caseArtifactUrl(details.case_id, artifact.id);
      grid.append(link);
    });
    refs.inspectorContent.replaceChildren(inspectorHeader("Artifact manifest", "Saved evidence files", "Each link resolves only through a verified local manifest."), evidenceBlock("Artifacts", grid));
    return;
  }
  refs.inspectorContent.replaceChildren(
    inspectorHeader("Technical envelope", "Bounded runtime", "Implementation state and collection limitations, not a conclusion about ownership."),
    evidenceBlock("Runtime", factList([
      ["Source", details.source_kind || "deterministic case"],
      ["Events", details.events?.length || 0],
      ["Agent steps", details.agent_steps || 0],
      ["Pending review", details.pending_review_count || 0],
    ])),
  );
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
  const actions = el("optgroup");
  actions.label = "Actions";
  const walkthrough = el("option", "", "New safe review walkthrough…");
  walkthrough.value = "action:new-review";
  actions.append(walkthrough);
  refs.workspaceSelector.append(actions);
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
  const caseIndicators = new Map(view.cases.map((item) => [item.case_id, item.gambling_indicator_count]));
  view.runs = runsResult.status === "fulfilled"
    ? (runsResult.value.runs || []).map((item) => ({
      ...item,
      gambling_indicator_count: caseIndicators.get(item.source_case_id),
    }))
    : [];
  renderSelector();
  renderRecentCases();
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
  showScreen("landing");
  setStatus(`${view.runs.length} investigations · ${view.cases.length} saved captures · ready`);
  try {
    const active = await requestJson("/api/investigation-jobs/active");
    if (active.job) void monitorInvestigationJob(active.job.job_id);
  } catch {
    // Read-only deployments do not expose investigation jobs.
  }
}

refs.scanForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const seedUrl = refs.seedInput.value.trim();
  setScanActive(true);
  setStatus("Creating an isolated, recoverable investigation job…");
  try {
    const job = await postJson("/api/investigation-jobs", {
      seed_url: seedUrl,
      investigation_name: refs.investigationName.value.trim(),
      investigation_mode: "guided",
    });
    renderInvestigationProgress(job);
    await monitorInvestigationJob(job.job_id);
  } catch (error) {
    toast(error.message, "error");
    setStatus(`Capture stopped safely · ${error.message}`);
    setScanActive(false);
  }
});

refs.brandHome.addEventListener("click", () => showScreen("landing"));
refs.newInvestigation.addEventListener("click", () => {
  showScreen("landing");
  refs.seedInput.focus();
});
refs.landingNewInvestigation.addEventListener("click", () => {
  document.getElementById("investigation-start")?.scrollIntoView({ behavior: reduceMotion ? "auto" : "smooth", block: "start" });
  refs.seedInput.focus();
});
refs.scanWorkspaceButton.addEventListener("click", () => {
  if (view.scanWorkspaceId) void loadRun(view.scanWorkspaceId);
});
refs.openSummary.addEventListener("click", () => {
  if (!view.currentDetails) return;
  renderSummary();
  showScreen("summary");
});
refs.backToGraph.addEventListener("click", () => showScreen("workspace"));
refs.inspectorTabs.forEach((button) => {
  button.addEventListener("click", () => renderInspectorTab(button.dataset.inspectorTab || "evidence"));
});

refs.caseSearch.addEventListener("input", () => {
  view.caseQuery = refs.caseSearch.value.trim();
  renderRecentCases();
});
refs.caseSort.addEventListener("change", renderRecentCases);
refs.caseFilters.forEach((button) => {
  button.addEventListener("click", () => {
    view.caseFilter = button.dataset.caseFilter || "all";
    refs.caseFilters.forEach((item) => {
      const active = item === button;
      item.classList.toggle("active", active);
      item.setAttribute("aria-pressed", String(active));
    });
    renderRecentCases();
  });
});
refs.caseGridView.addEventListener("click", () => {
  view.caseLayout = "grid";
  refs.caseGridView.classList.add("active");
  refs.caseGridView.setAttribute("aria-pressed", "true");
  refs.caseListView.classList.remove("active");
  refs.caseListView.setAttribute("aria-pressed", "false");
  renderRecentCases();
});
refs.caseListView.addEventListener("click", () => {
  view.caseLayout = "list";
  refs.caseListView.classList.add("active");
  refs.caseListView.setAttribute("aria-pressed", "true");
  refs.caseGridView.classList.remove("active");
  refs.caseGridView.setAttribute("aria-pressed", "false");
  renderRecentCases();
});

refs.workspaceSelector.addEventListener("change", () => {
  const [kind, id] = refs.workspaceSelector.value.split(":", 2);
  if (kind === "case" && id) void loadCase(id);
  if (kind === "run" && id) void loadRun(id);
  if (kind === "action" && id === "new-review") {
    refs.workspaceSelector.disabled = true;
    setStatus("Creating a safe local Page A → Page B walkthrough…");
    void postJson("/api/mvp/runs", {
      scenario_id: "redirect-new-tab",
      collection_mode: "synthetic_fixture",
    }).then(async (created) => {
      await refreshIndexes();
      await loadRun(created.workspace_id);
      toast("Safe review walkthrough created from reserved fixture evidence.", "success");
    }).catch((error) => {
      toast(error.message, "error");
      renderSelector();
    }).finally(() => {
      refs.workspaceSelector.disabled = false;
    });
  }
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
refs.timelineScrubber.addEventListener("input", () => {
  stopReplay();
  const index = Number(refs.timelineScrubber.value);
  const item = view.timeline[index];
  if (!item) return;
  view.playbackCutoff = item.sequence;
  setActiveTimeline(index);
  const target = view.nodeById.get(item.targetId);
  if (target) selectNode(target, true);
  else if (view.currentKind === "run" && item.event) renderRunEventInspector(view.currentDetails, item.event);
});

const resizeObserver = new ResizeObserver(() => {
  resizeCanvas();
  fitGraph();
});
resizeObserver.observe(refs.graphCanvas);
resizeCanvas();
window.requestAnimationFrame(drawFrame);
void boot();
