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
      button.append(node("span", "case-meta", "INTEGRITY ERROR"));
    } else {
      button.append(node("span", "case-meta", entry.final_url_display || "NO FINAL URL"));
      button.addEventListener("click", () => loadCase(entry.case_id, button));
    }
    caseList.append(button);
  }
}

function metric(label, value) {
  const card = node("div", "metric");
  card.append(node("span", "", label), node("strong", "", value));
  return card;
}

function dataRow(label, value) {
  const row = node("div", "data-row");
  row.append(node("span", "label", label), node("span", "value", value));
  return row;
}

function panel(title, subtitle) {
  const section = node("section", "panel");
  const heading = node("div", "panel-heading");
  heading.append(node("h3", "", title));
  if (subtitle) heading.append(node("p", "", subtitle));
  section.append(heading);
  return section;
}

function renderCase(details) {
  caseView.replaceChildren();
  const header = node("header", "case-header");
  const heading = node("div", "");
  heading.append(node("p", "eyebrow", "VERIFIED EVIDENCE PACKAGE"));
  heading.append(node("h2", "", details.case_id));
  heading.append(node("p", "case-url", details.final_url_display || "No final URL recorded"));
  const stamp = node("span", "stamp", "NEEDS HUMAN REVIEW");
  header.append(heading, stamp);
  caseView.append(header);

  const metrics = node("div", "overview-grid");
  metrics.append(
    metric("CAPTURE OUTCOME", details.capture_outcome || "unknown"),
    metric("PAGES", details.page_count),
    metric("CANDIDATE LEADS", details.candidates.length),
  );
  caseView.append(metrics);

  const evidence = panel("Evidence inventory", "Artifact IDs resolve through the verified manifest.");
  const evidenceRows = node("div", "data-list");
  for (const record of details.evidence) {
    evidenceRows.append(dataRow(`${record.type} · ${record.id}`, record.source_url_display));
  }
  evidence.append(evidenceRows);
  caseView.append(evidence);

  const screenshotPage = details.pages.find((page) => page.screenshot_evidence_id);
  if (screenshotPage) {
    const preview = panel("Rendered evidence", "Local screenshot preview only; no remote content is loaded.");
    const frame = node("div", "screenshot-frame");
    const image = document.createElement("img");
    image.alt = `Stored screenshot for ${screenshotPage.id}`;
    image.src = artifactUrl(details.case_id, screenshotPage.screenshot_evidence_id);
    frame.append(image);
    preview.append(frame, node("p", "artifact-note", "Captured HTML is available only as a text/plain attachment via its evidence record."));
    caseView.append(preview);
  }

  const entityPanel = panel("Observed entities", "Display values are redacted where a URL token or phone number could be sensitive.");
  const entities = node("div", "data-list");
  if (details.entities.length === 0) {
    entities.append(node("p", "muted", "No usable target-content entities were extracted."));
  } else {
    for (const entity of details.entities) entities.append(dataRow(entity.type, entity.display_value));
  }
  entityPanel.append(entities);
  caseView.append(entityPanel);

  const candidatePanel = panel("Pending candidate leads", "Priority is a collection triage input, not a mirror or ownership conclusion.");
  if (details.candidates.length === 0) {
    candidatePanel.append(node("p", "muted", "No pending candidates in this case package."));
  } else {
    for (const candidate of details.candidates) {
      const row = node("article", "candidate");
      const top = node("div", "candidate-topline");
      top.append(node("span", "candidate-host", candidate.hostname), node("span", "priority", `PRIORITY ${candidate.priority_score}`));
      row.append(top);
      for (const reason of candidate.reasons) row.append(node("span", "reason-chip", `${reason.reason_type} · ${reason.weight}`));
      candidatePanel.append(row);
    }
  }
  caseView.append(candidatePanel);

  const provenance = panel("Integrity chain", "Every visualized fact derives from the verified local package.");
  const chain = node("div", "data-list");
  chain.append(dataRow("CASE MANIFEST", details.case_manifest_sha256));
  if (details.graph) chain.append(dataRow("GRAPH", `${details.graph.node_count} nodes · ${details.graph.edge_count} edges`));
  provenance.append(chain);
  caseView.append(provenance);
}

async function loadCase(caseId, activeButton) {
  for (const button of caseList.querySelectorAll("button")) button.classList.remove("active");
  activeButton.classList.add("active");
  setStatus(`Verifying ${caseId}…`);
  try {
    renderCase(await requestJson(`/api/cases/${encodeURIComponent(caseId)}`));
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
