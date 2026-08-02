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
