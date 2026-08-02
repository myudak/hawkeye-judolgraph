const caseList = document.getElementById("case-list");
const caseView = document.getElementById("case-view");
const caseCount = document.getElementById("case-count");
const statusLine = document.getElementById("status-line");

function node(tag, className, text) {
  const element = document.createElement(tag);
  if (className) element.className = className;
  if (text !== undefined && text !== null) element.textContent = String(text);
  return element;
}

function artifactUrl(caseId, evidenceId) {
  return `/api/cases/${encodeURIComponent(caseId)}/artifacts/${encodeURIComponent(evidenceId)}`;
}

function artifactReference(caseId, evidenceId, available, label) {
  const display = label || `${caseId} / ${evidenceId}`;
  if (!available || !caseId) {
    return node("span", "missing-reference", `${display} · unavailable in this console`);
  }
  const link = node("a", "artifact-link", display);
  link.href = artifactUrl(caseId, evidenceId);
  link.title = "Open the verified local artifact in its safe response representation";
  return link;
}

async function requestJson(path) {
  const response = await fetch(path, { credentials: "same-origin", cache: "no-store" });
  if (!response.ok) throw new Error(`Request failed (${response.status})`);
  return response.json();
}

function setStatus(message) {
  statusLine.textContent = message;
}

function renderError(message) {
  caseView.replaceChildren(node("div", "error-card", message));
}

function renderCaseIndex(cases) {
  caseList.replaceChildren();
  caseCount.textContent = cases.length;
  for (const entry of cases) {
    const button = node("button", "case-button");
    button.type = "button";
    button.append(node("span", "case-id", entry.case_id));
    if (entry.integrity === "error") {
      button.classList.add("error");
      button.disabled = true;
      button.append(node("span", "case-meta", "INTEGRITY ERROR · NOT DISPLAYED"));
    } else {
      button.append(node("span", "case-meta", entry.final_url_display || "NO FINAL URL"));
      button.addEventListener("click", () => loadCase(entry.case_id, button));
    }
    caseList.append(button);
  }
}

function metric(label, value, detail) {
  const card = node("div", "metric");
  card.append(node("span", "metric-label", label), node("strong", "", value));
  if (detail) card.append(node("span", "metric-detail", detail));
  return card;
}

function panel(title, subtitle, id) {
  const section = node("section", "panel");
  if (id) section.setAttribute("aria-labelledby", id);
  const heading = node("div", "panel-heading");
  const headingText = node("div", "");
  const headingElement = node("h3", "", title);
  if (id) headingElement.id = id;
  headingText.append(headingElement);
  if (subtitle) headingText.append(node("p", "panel-subtitle", subtitle));
  heading.append(headingText);
  section.append(heading);
  return section;
}

function table(headers, rows, className) {
  const wrapper = node("div", "table-wrap");
  const element = node("table", className || "data-table");
  const head = document.createElement("thead");
  const headRow = document.createElement("tr");
  for (const header of headers) headRow.append(node("th", "", header));
  head.append(headRow);
  const body = document.createElement("tbody");
  for (const values of rows) {
    const row = document.createElement("tr");
    for (const value of values) {
      const cell = document.createElement("td");
      if (value instanceof Node) cell.append(value);
      else cell.textContent = value === null || value === undefined ? "—" : String(value);
      row.append(cell);
    }
    body.append(row);
  }
  element.append(head, body);
  wrapper.append(element);
  return wrapper;
}

function note(kind, title, message) {
  const aside = node("aside", `notice ${kind}`);
  aside.setAttribute("role", "note");
  aside.append(node("strong", "", title), node("p", "", message));
  return aside;
}

function textList(items, emptyMessage) {
  if (!items || items.length === 0) return node("p", "muted", emptyMessage);
  const list = node("ul", "text-list");
  for (const item of items) list.append(node("li", "", item));
  return list;
}

function formatScore(value) {
  return typeof value === "number" ? value.toFixed(1) : "—";
}

function contentState(details) {
  if (details.content_usable === true) return "Usable canonical content is available.";
  if (details.content_usable === false) return "No usable target content was classified; evidence remains preserved.";
  return "Canonical content usability was not recorded.";
}

function limitText(limits) {
  if (!limits) return "No crawl-configuration record is available in this package.";
  return `Bounded to depth ${limits.max_depth}, ${limits.max_pages_total} pages, and ${limits.max_redirects_per_page} redirects per page.`;
}

function renderCaseHeader(details) {
  const header = node("header", "case-header");
  const heading = node("div", "");
  heading.append(node("p", "eyebrow", "VERIFIED EVIDENCE PACKAGE"));
  heading.append(node("h2", "", details.case_id));
  heading.append(node("p", "case-url", details.final_url_display || "No final URL recorded"));
  const stamp = node("div", "stamp-group");
  stamp.append(node("span", "stamp", "REVIEW STATUS: NEEDS REVIEW"));
  stamp.append(node("span", "stamp-note", "No human conclusion is recorded here."));
  header.append(heading, stamp);
  return header;
}

function renderInvestigationPath(details) {
  const workflow = panel(
    "Investigation path",
    "A display of recorded stages—not an instruction to collect, compare, or conclude.",
    "investigation-path",
  );
  const path = node("ol", "investigation-path");
  const comparisonSummary = details.comparisons.length
    ? `${details.comparisons.length} stored offline comparison result(s) are available.`
    : "No stored offline comparison result is attached; this console will not create one.";
  const stages = [
    ["01", "Seed", details.seed_url_display || "No safe seed URL is available.", "Recorded as a local case input; the console does not revisit it."],
    ["02", "Bounded capture", contentState(details), limitText(details.collection_limits)],
    ["03", "Extracted observations", `${details.entities.length} deterministic observation(s) displayed.`, "No entity appears unless it was derived from verified saved evidence."],
    ["04", "Evidence graph", details.graph ? `${details.graph.edge_count} relationship record(s) are available.` : "No graph artifact is available.", "Graph rows distinguish structural records from observed-evidence relationships."],
    ["05", "Pending leads", `${details.candidates.length} pending lead(s) are available.`, "Relationship: not determined. A lead does not authorize navigation."],
    ["06", "Offline comparisons", comparisonSummary, "Evidence-similarity scores remain inputs for review, never ownership probabilities."],
    ["07", "Human review", "Review status: needs review.", "This console records no conclusion, ownership claim, or legal finding."],
  ];
  for (const [number, title, happened, limit] of stages) {
    const item = node("li", "path-step");
    item.append(node("span", "path-number", number));
    const content = node("div", "path-content");
    content.append(node("h4", "", title), node("p", "", happened), node("p", "path-limit", limit));
    item.append(content);
    path.append(item);
  }
  workflow.append(path);
  return workflow;
}

function renderWarnings(details) {
  const notices = [];
  if (details.content_usable === false) {
    notices.push(note("warning", "Capture limitation", "This case has no usable canonical target content. Missing observations must not be read as absence of activity."));
  }
  if (details.classification_reasons.length) {
    notices.push(note("neutral", "Recorded capture reasons", details.classification_reasons.join(" · ")));
  }
  if (details.diagnostic) {
    const diagnostic = details.diagnostic;
    notices.push(note(
      "diagnostic",
      `Separate render diagnostic: ${diagnostic.status}`,
      `${diagnostic.checkpoint_count} fixed checkpoint(s), ${diagnostic.diagnostic_wait_budget_ms} ms wait budget, ${diagnostic.collection_mode} mode. This is noncanonical observational data.`,
    ));
  }
  if (details.diagnostic_integrity_warning) {
    notices.push(note("warning", "Diagnostic integrity warning", details.diagnostic_integrity_warning));
  }
  if (details.comparison_integrity_warning) {
    notices.push(note("warning", "Comparison integrity warning", "One or more configured comparison documents could not be verified and are not displayed."));
  }
  if (!notices.length) return null;
  const section = node("section", "notice-stack");
  section.setAttribute("aria-label", "Case limitations and integrity notices");
  section.append(...notices);
  return section;
}

function renderOverview(details) {
  const grid = node("div", "overview-grid");
  grid.append(
    metric("CAPTURE OUTCOME", details.capture_outcome || "unknown", `Navigation: ${details.navigation_status}`),
    metric("CANONICAL CONTENT", details.content_usable === true ? "USABLE" : "LIMITED", details.content_usable === true ? "Evidence may support extraction." : "Review capture limitations."),
    metric("PENDING LEADS", details.candidates.length, "Relationship: not determined."),
    metric("GRAPH RECORDS", details.graph ? details.graph.edge_count : 0, "Evidence graph relationships."),
  );
  return grid;
}

function renderPages(details) {
  const section = panel("Capture ledger", "Page-level outcome and artifact references from the verified case manifest.", "capture-ledger");
  const rows = details.pages.map((page) => [
    page.id,
    `Depth ${page.depth} · ${page.state}`,
    page.capture_outcome || "unknown",
    page.content_usable === true ? "usable" : "limited",
    page.html_evidence_id
      ? artifactReference(details.case_id, page.html_evidence_id, true, `HTML · ${page.html_evidence_id}`)
      : "No HTML artifact",
    page.screenshot_evidence_id
      ? artifactReference(details.case_id, page.screenshot_evidence_id, true, `Screenshot · ${page.screenshot_evidence_id}`)
      : "No screenshot artifact",
  ]);
  section.append(table(["Page", "Bounded state", "Outcome", "Content", "HTML evidence", "Screenshot evidence"], rows));
  return section;
}

function renderEvidence(details) {
  const section = panel("Evidence inventory", "Every artifact route resolves through a fresh verified manifest check.", "evidence-inventory");
  const rows = details.evidence.map((record) => [
    record.id,
    record.type,
    record.page_id || "—",
    record.source_url_display || "[invalid URL]",
    artifactReference(details.case_id, record.id, record.artifact_available, "Open safe artifact"),
  ]);
  section.append(table(["Evidence ID", "Type", "Page", "Inert source display", "Artifact"], rows));
  return section;
}

function renderScreenshot(details) {
  const screenshotPage = details.pages.find((page) => page.screenshot_evidence_id);
  if (!screenshotPage) return null;
  const section = panel("Rendered evidence preview", "A local screenshot artifact, not a live page and not an interactive surface.", "rendered-evidence");
  const frame = node("div", "screenshot-frame");
  const image = document.createElement("img");
  image.alt = `Stored screenshot evidence for ${screenshotPage.id}`;
  image.referrerPolicy = "no-referrer";
  image.src = artifactUrl(details.case_id, screenshotPage.screenshot_evidence_id);
  image.addEventListener("error", () => {
    frame.replaceChildren(note("warning", "Preview unavailable", "The screenshot artifact could not be rendered; inspect its verified local reference instead."));
  });
  frame.append(image);
  section.append(
    frame,
    node("p", "artifact-note", "Captured HTML is exposed only as a text/plain attachment. The console never inserts captured HTML into this page."),
  );
  return section;
}

function renderEntities(details) {
  const section = panel("Observed entities", "Deterministic extraction from saved HTML only. Display values are redacted and inert.", "observed-entities");
  if (!details.entities.length) {
    section.append(node("p", "muted", "No usable target-content entities were extracted from this package."));
    return section;
  }
  const rows = details.entities.map((entity) => [
    entity.id,
    entity.type,
    entity.display_value,
    artifactReference(details.case_id, entity.source_evidence_id, true, entity.source_evidence_id),
    entity.source_page_id || "—",
    entity.confidence.toFixed(2),
  ]);
  section.append(table(["Observation", "Type", "Inert display", "Supporting evidence", "Page", "Confidence"], rows));
  return section;
}

function renderGraph(details) {
  const section = panel("Evidence graph — accessible relationship table", "A deterministic table is the primary readable graph representation; color is not required to interpret it.", "evidence-graph");
  if (!details.graph || !details.graph.edges.length) {
    section.append(node("p", "muted", "No verified graph relationships are available in this case package."));
    return section;
  }
  const rows = details.graph.edges.map((edge) => [
    `${edge.source.label} (${edge.source.type})`,
    edge.type,
    `${edge.target.label} (${edge.target.type})`,
    edge.evidence
      ? artifactReference(edge.evidence.case_id, edge.evidence.evidence_id, edge.evidence.available, edge.evidence.evidence_id)
      : "Structural record · no extracted observation",
    edge.relationship_status === "observed_evidence" ? "Observed evidence" : "Structural record",
  ]);
  section.append(table(["Source node", "Relationship", "Target node", "Supporting evidence", "Relationship status"], rows, "graph-table"));
  return section;
}

function renderEvidenceRefs(refs) {
  const list = node("ul", "reference-list");
  if (!refs.length) {
    list.append(node("li", "", "No supporting artifact reference was recorded."));
    return list;
  }
  for (const reference of refs) {
    const label = reference.case_id
      ? `${reference.case_id} / ${reference.evidence_id}`
      : reference.evidence_id;
    const item = document.createElement("li");
    item.append(artifactReference(reference.case_id, reference.evidence_id, reference.available, label));
    if (reference.observation_id) item.append(node("span", "reference-note", ` · observation ${reference.observation_id}`));
    list.append(item);
  }
  return list;
}

function renderCandidates(details) {
  const section = panel("Pending candidate leads", "Priority is a deterministic triage input. Relationship: not determined.", "pending-leads");
  if (details.candidate_policy_version) {
    section.append(node("p", "policy-note", `Candidate policy: ${details.candidate_policy_version}`));
  }
  if (!details.candidates.length) {
    section.append(node("p", "muted", "No pending candidate leads are present in this verified package."));
    return section;
  }
  for (const candidate of details.candidates) {
    const article = node("article", "candidate");
    const top = node("div", "candidate-topline");
    const title = node("div", "");
    title.append(node("h4", "candidate-host", candidate.hostname), node("p", "candidate-status", "Pending lead · Relationship: not determined"));
    top.append(title, node("span", "priority", `TRIAGE ${candidate.priority_score}`));
    article.append(top);
    const reasons = node("div", "reason-list");
    for (const reason of candidate.reasons) {
      const detail = node("details", "reason-detail");
      const summary = node("summary", "", `${reason.reason_type} · weight ${reason.weight}`);
      detail.append(summary, renderEvidenceRefs(reason.evidence_refs));
      if (reason.observation_ids.length) detail.append(node("p", "reference-note", `Observation IDs: ${reason.observation_ids.join(", ")}`));
      reasons.append(detail);
    }
    article.append(reasons);
    section.append(article);
  }
  return section;
}

function renderDiagnostic(details) {
  if (!details.diagnostic) return null;
  const diagnostic = details.diagnostic;
  const section = panel("Render diagnostic (separate from canonical evidence)", "This bounded measurement cannot replace stored HTML, screenshots, extraction, graph, or scoring.", "render-diagnostic");
  const rows = [
    ["Diagnostic status", diagnostic.status],
    ["Collection mode", diagnostic.collection_mode],
    ["Source page", diagnostic.source_page_id],
    ["Fixed checkpoint count", diagnostic.checkpoint_count],
    ["Diagnostic wait budget", `${diagnostic.diagnostic_wait_budget_ms} ms`],
  ];
  section.append(table(["Field", "Recorded value"], rows));
  const evidenceHeading = node("p", "policy-note", "Canonical evidence references used only to tie this separate observation to the case:");
  section.append(evidenceHeading, renderEvidenceRefs(diagnostic.evidence_refs));
  return section;
}

function renderComparisons(details) {
  const section = panel("Offline comparison results", "Evidence-similarity scores are deterministic review inputs, never ownership probabilities.", "offline-comparisons");
  if (!details.comparisons.length) {
    section.append(node("p", "muted", "No separately stored, locally verified comparison document is configured for this case."));
    section.append(node("p", "policy-note", "The console never runs a comparison automatically and never contacts either domain."));
    return section;
  }
  for (const comparison of details.comparisons) {
    const card = node("article", "comparison");
    card.append(node("h4", "", `${comparison.left_case_id} ↔ ${comparison.right_case_id}`));
    const summary = node("div", "comparison-summary");
    summary.append(
      metric("EVIDENCE-SIMILARITY SCORE", `${formatScore(comparison.evidence_similarity_score)} / 100`, "Not a probability or ownership claim."),
      metric("REVIEW STATUS", comparison.review_status.toUpperCase(), "Human conclusion not recorded."),
    );
    card.append(summary);
    card.append(node("p", "policy-note", `Comparator: ${comparison.comparator_version} · Policy: ${comparison.scoring_policy_version}`));
    const rows = comparison.components.map((component) => [
      component.name,
      `${formatScore(component.score)} · weight ${component.weight.toFixed(2)}`,
      component.available ? component.status : `unavailable · ${component.status}`,
      component.evidence_refs.length
        ? artifactReference(
            component.evidence_refs[0].case_id,
            component.evidence_refs[0].evidence_id,
            component.evidence_refs[0].available,
            `${component.evidence_refs.length} evidence ref(s)`,
          )
        : "No evidence reference",
      component.entity_refs.length
        ? component.entity_refs.map((reference) => `${reference.entity_id} (${reference.type})`).join(", ")
        : "No entity reference",
    ]);
    card.append(table(["Component", "Score", "Availability", "Artifact provenance", "Entity provenance"], rows));
    if (comparison.warnings.length) card.append(textList(comparison.warnings, ""));
    card.append(node("p", "comparison-manifest", `Input manifests: ${comparison.left_case_manifest_sha256} · ${comparison.right_case_manifest_sha256}`));
    section.append(card);
  }
  return section;
}

function renderIntegrity(details) {
  const section = panel("Integrity chain and review boundary", "Every displayed fact is traceable to a verified local package or a separately verified companion document.", "integrity-chain");
  const rows = [
    ["Case ID", details.case_id],
    ["Case manifest", details.case_manifest_sha256],
    ["Canonical evidence", `${details.evidence.length} artifact record(s) verified before display`],
    ["Graph artifact", details.graph ? `${details.graph.schema_version || "schema not recorded"} · ${details.graph.node_count} nodes / ${details.graph.edge_count} edges` : "Not available"],
    ["Human conclusion", "Not recorded · review status remains needs review"],
  ];
  section.append(table(["Provenance field", "Value"], rows));
  section.append(note("neutral", "Limit of this console", "It does not collect, navigate, submit, fetch external sources, infer ownership, or record a human decision."));
  return section;
}

function renderCase(details) {
  caseView.replaceChildren();
  caseView.append(renderCaseHeader(details));
  const warnings = renderWarnings(details);
  if (warnings) caseView.append(warnings);
  caseView.append(renderOverview(details));
  caseView.append(renderInvestigationPath(details));
  caseView.append(renderPages(details));
  caseView.append(renderEvidence(details));
  const screenshot = renderScreenshot(details);
  if (screenshot) caseView.append(screenshot);
  caseView.append(renderEntities(details));
  caseView.append(renderGraph(details));
  caseView.append(renderCandidates(details));
  const diagnostic = renderDiagnostic(details);
  if (diagnostic) caseView.append(diagnostic);
  caseView.append(renderComparisons(details));
  caseView.append(renderIntegrity(details));
}

async function loadCase(caseId, activeButton) {
  for (const button of caseList.querySelectorAll("button")) {
    button.classList.remove("active");
    button.removeAttribute("aria-current");
  }
  if (activeButton) {
    activeButton.classList.add("active");
    activeButton.setAttribute("aria-current", "true");
  }
  setStatus(`Verifying ${caseId}…`);
  try {
    renderCase(await requestJson(`/api/cases/${encodeURIComponent(caseId)}`));
    caseView.focus({ preventScroll: true });
    setStatus(`Verified local case: ${caseId}`);
  } catch (error) {
    renderError("This case could not be displayed because its local evidence integrity check failed.");
    setStatus(error.message);
  }
}

async function bootstrap() {
  try {
    const payload = await requestJson("/api/cases");
    renderCaseIndex(payload.cases);
    const first = payload.cases.find((entry) => entry.integrity === "verified");
    if (first) {
      const firstButton = caseList.querySelector("button:not([disabled])");
      loadCase(first.case_id, firstButton);
    } else {
      setStatus("No verified completed cases found.");
    }
  } catch (error) {
    renderError("The local evidence index could not be loaded.");
    setStatus(error.message);
  }
}

bootstrap();

const mvpWorkspace = document.getElementById("mvp-workspace");
const mvpRunForm = document.getElementById("mvp-run-form");
const mvpScenario = document.getElementById("mvp-scenario");
const mvpRunList = document.getElementById("mvp-run-list");
const mvpRunView = document.getElementById("mvp-run-view");
let selectedMvpRun = null;

async function mutateJson(path, payload) {
  const response = await fetch(path, {
    method: "POST",
    credentials: "same-origin",
    cache: "no-store",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload || {}),
  });
  if (!response.ok) throw new Error(`Mutation rejected (${response.status})`);
  return response.json();
}

function mvpBadge(label, value) {
  return metric(label, value || "—", "Persisted, replayable state");
}

function renderMvpGraph(details, query = "") {
  const section = panel(
    "Progressive evidence graph",
    "Graph truth is reduced from stored events; animations are a separate queue.",
    "mvp-graph",
  );
  const controls = node("div", "graph-controls");
  const search = document.createElement("input");
  search.type = "search";
  search.placeholder = "Search/focus graph nodes";
  search.value = query;
  search.setAttribute("aria-label", "Search graph nodes");
  controls.append(search, node("span", "policy-note", "Reduced-motion follows system preference"));
  section.append(controls);
  const normalizedQuery = query.trim().toLowerCase();
  const visibleNodes = details.graph.nodes.filter((item) =>
    !normalizedQuery || `${item.label} ${item.kind} ${item.status}`.toLowerCase().includes(normalizedQuery)
  );
  const visibleIds = new Set(visibleNodes.map((item) => item.id));
  const minimap = node("div", "graph-minimap");
  minimap.setAttribute("aria-label", "Graph minimap");
  for (const item of visibleNodes) {
    const chip = node("span", `graph-node ${item.status}`, `${item.kind}: ${item.label}`);
    chip.dataset.nodeId = item.id;
    minimap.append(chip);
  }
  section.append(minimap);
  const edges = details.graph.edges.filter((edge) =>
    !normalizedQuery || visibleIds.has(edge.source) || visibleIds.has(edge.target)
  );
  section.append(table(
    ["Source", "Relation", "Target", "Appearance", "Evidence"],
    edges.map((edge) => [
      edge.source,
      edge.relation,
      edge.target,
      edge.appearance,
      edge.supporting_observation_ids.join(", ") || edge.supporting_event_ids.join(", "),
    ]),
    "graph-table",
  ));
  search.addEventListener("input", () => {
    const replacement = renderMvpGraph(details, search.value);
    section.replaceWith(replacement);
    replacement.querySelector("input")?.focus();
  });
  return section;
}

function renderMvpObservations(details) {
  const section = panel(
    "Evidence inspector",
    "Normalized observations retain source event and artifact IDs; fixture artifacts are inert JSON.",
    "mvp-evidence",
  );
  const observations = details.events.filter((event) => event.kind === "observation.created");
  section.append(table(
    ["Observation", "Type", "Normalized value", "Artifact", "Event"],
    observations.map((event) => [
      event.payload.observation_id,
      event.payload.observation_type,
      event.payload.normalized_value,
      event.payload.artifact_id,
      `#${event.sequence} · ${event.event_id}`,
    ]),
  ));
  const artifacts = node("div", "artifact-actions");
  for (const artifact of details.artifacts) {
    const link = node("a", "artifact-link", `${artifact.name} · ${artifact.bytes} bytes`);
    link.href = `/api/mvp/runs/${encodeURIComponent(details.workspace_id)}/artifacts/${encodeURIComponent(artifact.name)}`;
    artifacts.append(link);
  }
  section.append(artifacts);
  return section;
}

function renderMvpTimeline(details) {
  const section = panel(
    "Agent and tool event timeline",
    "Monotonic events are persisted before this view is rendered.",
    "mvp-timeline",
  );
  section.append(table(
    ["Seq", "Kind", "Causation", "Recorded payload"],
    details.events.map((event) => [
      event.sequence,
      event.kind,
      event.causation_event_id || "root",
      JSON.stringify(event.payload).slice(0, 240),
    ]),
  ));
  return section;
}

function renderMvpCausalPath(details) {
  const section = panel(
    "Causal tree / path",
    "Every child points to the event that caused it when a direct cause exists.",
    "mvp-causal",
  );
  section.append(table(
    ["Event", "Caused by"],
    details.graph.causal_links.map((item) => [item.event_id, item.causation_event_id || "root"]),
  ));
  return section;
}

function renderMvpReview(details) {
  const section = panel(
    "Candidate assertion and human review",
    "Verified means the selected evidence supports only the stated relationship.",
    "mvp-review",
  );
  if (details.lead_status === "waiting_for_approval") {
    section.append(note(
      "warning",
      "Candidate waiting for approval",
      "Real-world mode does not recollect Page B automatically.",
    ));
    const approve = node("button", "action-button", "Approve recollection boundary");
    approve.type = "button";
    approve.addEventListener("click", async () => {
      await mutateJson(`/api/mvp/runs/${encodeURIComponent(details.workspace_id)}/approve`, {});
      await loadMvpRun(details.workspace_id);
    });
    section.append(approve);
    return section;
  }
  if (!details.assertion) {
    section.append(node("p", "muted", "No evidence-backed candidate assertion was proposed."));
    return section;
  }
  section.append(table(
    ["Assertion", "Relation", "Subject", "Object", "Status"],
    [[
      details.assertion.assertion_id,
      details.assertion.assertion_type,
      details.assertion.subject,
      details.assertion.object,
      details.current_assertion_status,
    ]],
  ));
  section.append(node(
    "p",
    "policy-note",
    `Supporting observations: ${details.assertion.supporting_observation_ids.join(", ")}`,
  ));
  const form = node("form", "review-form");
  const label = document.createElement("input");
  label.required = true;
  label.maxLength = 200;
  label.placeholder = "Reviewer label";
  label.setAttribute("aria-label", "Reviewer label");
  const reason = document.createElement("textarea");
  reason.required = true;
  reason.maxLength = 2000;
  reason.placeholder = "Evidence-based review reason";
  reason.setAttribute("aria-label", "Review reason");
  const outcome = document.createElement("select");
  for (const value of ["verified", "rejected", "needs_more_evidence", "duplicate", "uncertain"]) {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = value.replaceAll("_", " ");
    outcome.append(option);
  }
  const submit = node("button", "action-button", "Append review event");
  submit.type = "submit";
  form.append(label, outcome, reason, submit);
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    submit.disabled = true;
    try {
      await mutateJson(`/api/mvp/runs/${encodeURIComponent(details.workspace_id)}/reviews`, {
        assertion_id: details.assertion.assertion_id,
        outcome: outcome.value,
        reviewer_label: label.value,
        reason: reason.value,
      });
      await loadMvpRun(details.workspace_id);
    } finally {
      submit.disabled = false;
    }
  });
  section.append(form);
  if (details.reviews.length) {
    section.append(table(
      ["Version", "Outcome", "Reviewer", "Reason", "Timestamp"],
      details.reviews.map((review) => [
        `${review.previous_version} → ${review.new_version}`,
        review.outcome,
        review.reviewer_label,
        review.reason,
        review.occurred_at,
      ]),
    ));
  }
  return section;
}

function renderMvpRun(details) {
  const header = node("header", "case-header");
  const heading = node("div", "");
  heading.append(
    node("p", "eyebrow", "SYNTHETIC · EVENT-BUILT · REVIEWABLE"),
    node("h2", "", details.case_id),
    node("p", "case-url", details.run_id),
  );
  header.append(heading, node("span", "stamp", `STATUS: ${details.current_assertion_status || details.lead_status || "completed"}`));
  const metrics = node("div", "overview-grid");
  metrics.append(
    mvpBadge("AGENT MODE", details.agent_mode),
    mvpBadge("PAGE B", details.lead_status),
    mvpBadge("EVENTS", details.events.length),
    mvpBadge("GRAPH EDGES", details.graph.edges.length),
  );
  mvpRunView.replaceChildren(
    header,
    metrics,
    renderMvpGraph(details),
    renderMvpObservations(details),
    renderMvpReview(details),
    renderMvpTimeline(details),
    renderMvpCausalPath(details),
  );
}

async function loadMvpRun(workspaceId) {
  selectedMvpRun = workspaceId;
  const details = await requestJson(`/api/mvp/runs/${encodeURIComponent(workspaceId)}`);
  renderMvpRun(details);
}

async function refreshMvpRuns() {
  const payload = await requestJson("/api/mvp/runs");
  mvpRunList.replaceChildren();
  for (const run of payload.runs) {
    const button = node("button", "case-button");
    button.type = "button";
    button.append(
      node("span", "case-id", run.case_id),
      node("span", "case-meta", `${run.agent_mode} · ${run.lead_status || "no lead"}`),
    );
    button.addEventListener("click", () => loadMvpRun(run.workspace_id));
    mvpRunList.append(button);
  }
}

async function bootstrapMvp() {
  try {
    const payload = await requestJson("/api/mvp/scenarios");
    mvpWorkspace.hidden = false;
    for (const scenario of payload.scenarios) {
      const option = document.createElement("option");
      option.value = scenario.scenario_id;
      option.textContent = `${scenario.ordinal}. ${scenario.name}`;
      mvpScenario.append(option);
    }
    await refreshMvpRuns();
    mvpRunForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      const button = mvpRunForm.querySelector("button");
      button.disabled = true;
      button.textContent = "Collecting…";
      try {
        const created = await mutateJson("/api/mvp/runs", {
          scenario_id: mvpScenario.value,
          collection_mode: "synthetic_fixture",
        });
        await refreshMvpRuns();
        await loadMvpRun(created.workspace_id);
      } catch (error) {
        mvpRunView.replaceChildren(node("div", "error-card", error.message));
      } finally {
        button.disabled = false;
        button.textContent = "Collect + expand safely";
      }
    });
    setInterval(() => {
      if (selectedMvpRun && !document.hidden) loadMvpRun(selectedMvpRun).catch(() => {});
    }, 3000);
  } catch (_error) {
    mvpWorkspace.hidden = true;
  }
}

bootstrapMvp();
