import type { ApiClient } from "@/api/live-client"
import type { InvestigationJob, ReviewRecord, RunDetails } from "@/api/types"
import fixtures from "@/demo/fixtures.json"
import { demoScenarios } from "@/demo/scenarios"

const samples = fixtures.runs as RunDetails[]
const assetNames = fixtures.assets as Record<string, Record<string, string>>
const assetUrls = import.meta.glob<string>("./assets/*", {
  query: "?url",
  import: "default",
  eager: true,
})
const storageKey = "hawk-eye-demo-v1"
const assertionId = "demo-public-link"
const stages = [
  "validating_seed",
  "capturing_page",
  "preserving_artifacts",
  "extracting_evidence",
  "verifying_evidence",
  "building_graph",
  "completed",
]
const stageDuration = 1000
const outcomes = [
  "verified",
  "rejected",
  "needs_more_evidence",
  "duplicate",
  "uncertain",
]

interface DemoState {
  jobs: Record<string, number>
  activeId: string | null
  approved: boolean
  reviews: ReviewRecord[]
}

function emptyState(): DemoState {
  return { jobs: {}, activeId: null, approved: false, reviews: [] }
}

function knownId(id: string): boolean {
  return demoScenarios.some((scenario) => scenario.id === id)
}

function restore(): DemoState {
  try {
    const value = JSON.parse(sessionStorage.getItem(storageKey) ?? "null")
    if (!value || typeof value !== "object") return emptyState()
    const jobs: Record<string, number> = {}
    for (const scenario of demoScenarios) {
      const started = value.jobs?.[scenario.id]
      if (
        typeof started === "number" &&
        Number.isFinite(started) &&
        started > 0
      )
        jobs[scenario.id] = started
    }
    const reviews: ReviewRecord[] = Array.isArray(value.reviews)
      ? value.reviews
          .slice(-50)
          .filter(
            (item: ReviewRecord) =>
              item &&
              item.assertion_id === assertionId &&
              typeof item.review_id === "string" &&
              outcomes.includes(item.outcome) &&
              typeof item.reviewer_label === "string" &&
              item.reviewer_label.length <= 200 &&
              typeof item.reason === "string" &&
              item.reason.length <= 2000
          )
      : []
    return {
      jobs,
      activeId:
        typeof value.activeId === "string" && knownId(value.activeId)
          ? value.activeId
          : null,
      approved: value.approved === true,
      reviews: value.approved === true ? reviews : [],
    }
  } catch {
    return emptyState()
  }
}

let state: DemoState | undefined
const exports = new Map<string, string>()

function currentState(): DemoState {
  state ??= restore()
  return state
}

function save(): void {
  for (const url of exports.values()) URL.revokeObjectURL(url)
  exports.clear()
  try {
    sessionStorage.setItem(storageKey, JSON.stringify(currentState()))
  } catch {
    return
  }
}

export function resetDemo(): void {
  state = emptyState()
  save()
}

function requireSample(id: string): RunDetails {
  const sample = samples.find((item) => item.workspace_id === id)
  if (!sample)
    throw new Error("This demo only supports the supplied scenarios.")
  return structuredClone(sample)
}

function getRun(id: string): RunDetails {
  const run = requireSample(id)
  const local = currentState()
  if (id !== "demo-related" || !local.approved) return run
  const candidate = requireSample("demo-contact").source_case!
  candidate.pages = candidate.pages.slice(0, 1)
  candidate.page_count = 1
  candidate.evidence = candidate.evidence.filter(
    (item) => item.page_id === candidate.pages[0].id
  )
  candidate.observations = candidate.observations.filter(
    (item) => item.source_page_id === candidate.pages[0].id
  )
  if (candidate.gambling_indicators)
    candidate.gambling_indicators.reviewed_observation_count =
      candidate.observations.length
  const sourceNode = run.graph.nodes[0].id
  const targetNode = `page:${candidate.pages[0].id}`
  const sequence = run.events.length + 1
  run.events.push({
    event_id: "demo-approval",
    sequence,
    kind: "candidate_page.approved",
    payload: {
      collection_mode: "synthetic_fixture",
      url: candidate.seed_url_display,
    },
  })
  run.events.push({
    event_id: "demo-candidate-collected",
    sequence: sequence + 1,
    kind: "candidate_page.collected",
    payload: {
      collection_mode: "synthetic_fixture",
      case_id: candidate.case_id,
    },
  })
  run.events.push({
    event_id: "demo-assertion-proposed",
    sequence: sequence + 2,
    kind: "assertion.proposed",
    payload: { assertion_id: assertionId, assertion_type: "publicly_links_to" },
  })
  run.graph.nodes.push({
    id: targetNode,
    kind: "collected_page",
    label: candidate.seed_url_display!,
    status: "observed",
    attributes: {
      page: candidate.pages[0],
      page_id: candidate.pages[0].id,
      limitations: [fixtures.limitation],
    },
  })
  run.graph.animations?.push({ target_id: targetNode, sequence: sequence + 1 })
  const latest = local.reviews.at(-1)
  run.graph.edges.push({
    id: `assertion:${assertionId}`,
    source: sourceNode,
    target: targetNode,
    relation: "publicly_links_to",
    appearance:
      latest?.outcome === "verified"
        ? "solid_emphasized"
        : latest?.outcome === "rejected"
          ? "rejected"
          : "dashed",
    supporting_event_ids: ["demo-assertion-proposed"],
    evidence: {
      limitations: [
        fixtures.limitation,
        "A visible link does not establish ownership.",
      ],
    },
  })
  run.assertion = {
    assertion_id: assertionId,
    assertion_type: "publicly_links_to",
    subject_node_id: sourceNode,
    object_node_id: targetNode,
    supporting_observation_ids: run.source_case!.observations.map(
      (item) => item.id
    ),
    source_artifact_ids: run.source_case!.observations.map(
      (item) => item.source_artifact_id!
    ),
    limitations: [
      fixtures.limitation,
      "A visible link does not establish ownership.",
    ],
  }
  run.assertions = [run.assertion]
  run.current_assertion_status = latest?.outcome ?? "needs_review"
  run.assertion_statuses = { [assertionId]: run.current_assertion_status }
  const resolved =
    latest && ["verified", "rejected", "duplicate"].includes(latest.outcome)
  run.pending_review_count = resolved ? 0 : 1
  run.lead_status = resolved ? "reviewed" : "needs_review"
  run.pending_leads = []
  run.candidate_case_id = candidate.case_id
  run.candidate_case = candidate
  run.reviews = structuredClone(local.reviews)
  run.all_reviews = run.reviews
  for (const review of local.reviews) {
    run.events.push({
      event_id: review.review_id,
      sequence: run.events.length + 1,
      kind: "assertion.reviewed",
      occurred_at: review.occurred_at,
      payload: { ...review, collection_mode: "synthetic_fixture" },
    })
  }
  return run
}

function getJob(id: string): InvestigationJob {
  requireSample(id)
  const started = currentState().jobs[id]
  if (!started)
    throw new Error("Sample playback was not started. Choose a scenario first.")
  const index = Math.min(
    stages.length - 1,
    Math.max(0, Math.floor((Date.now() - started) / stageDuration))
  )
  const run = getRun(id)
  const preview = {
    preview_id: `${id}-preview`,
    revision: 1,
    page_id: run.source_case!.pages[0].id,
    kind: "canonical" as const,
    verification: "persisted" as const,
    captured_at: run.source_case!.started_at ?? undefined,
    width: 1200,
    height: 760,
  }
  return {
    job_id: id,
    status: index === stages.length - 1 ? "completed" : "running",
    stage: stages[index],
    started_at: new Date(started).toISOString(),
    updated_at: new Date(started + index * stageDuration).toISOString(),
    deadline_seconds: stages.length,
    target: {
      seed_url: run.seed_url!,
      page_title: run.source_case!.page_title!,
      investigation_name: "Sample playback",
    },
    history: stages.slice(0, index + 1).map((stage, position) => ({
      stage,
      at: new Date(started + position * stageDuration).toISOString(),
    })),
    visual_state: {
      revision: index >= 1 ? 1 : 0,
      previews: index >= 1 ? [preview] : [],
      latest_preview: index >= 1 ? preview : undefined,
    },
    result: index === stages.length - 1 ? run : null,
  }
}

export const demoApi: ApiClient = {
  listCases: async () => ({
    cases: samples.map((run) => structuredClone(run.source_case!)),
  }),
  listRuns: async () => ({
    runs: samples.map((run) => getRun(run.workspace_id)),
  }),
  capability: async () => ({
    state: "demo_replay",
    safe_to_enable_model_path: false,
  }),
  settings: async () => ({
    available: false,
    enabled: false,
    api_key_configured: false,
  }),
  updateSettings: async () => {
    throw new Error("Provider settings are unavailable in the demo.")
  },
  activeJob: async () => {
    const id = currentState().activeId
    const job = id && currentState().jobs[id] ? getJob(id) : null
    return { job: job?.status === "running" ? job : null }
  },
  getJob: async (id) => getJob(id),
  startJob: async (payload) => {
    const scenario = demoScenarios.find(
      (item) => item.seedUrl === payload.seed_url
    )
    if (!scenario)
      throw new Error("Choose one of the supplied sample scenarios.")
    const local = currentState()
    local.jobs[scenario.id] = Date.now()
    local.activeId = scenario.id
    if (scenario.id === "demo-related") {
      local.approved = false
      local.reviews = []
    }
    save()
    return getJob(scenario.id)
  },
  getCase: async (id) => {
    const run = samples.find((item) => item.source_case_id === id)
    if (!run) throw new Error("Unknown sample case.")
    return structuredClone(run.source_case!)
  },
  getRun: async (id) => getRun(id),
  createWalkthrough: async () => ({ workspace_id: "demo-contact" }),
  approveCandidate: async (id) => {
    requireSample(id)
    if (id !== "demo-related")
      throw new Error("This sample has no candidate awaiting approval.")
    currentState().approved = true
    save()
    return getRun(id)
  },
  appendReview: async (id, payload) => {
    const run = getRun(id)
    if (
      payload.assertion_id !== run.assertion?.assertion_id ||
      !outcomes.includes(payload.outcome)
    )
      throw new Error("Choose a valid sample assertion and review outcome.")
    const reviewer = payload.reviewer_label.trim()
    const reason = payload.reason.trim()
    if (!reviewer || reviewer.length > 200 || !reason || reason.length > 2000)
      throw new Error(
        "A reviewer label and evidence-bounded reason are required."
      )
    const local = currentState()
    if (local.reviews.length >= 50)
      throw new Error("Reset the demo before adding more sample reviews.")
    const version = local.reviews.length + 1
    local.reviews.push({
      review_id: `demo-review-${version}`,
      assertion_id: assertionId,
      outcome: payload.outcome,
      reviewer_label: reviewer,
      reason,
      occurred_at: new Date().toISOString(),
      previous_version: version - 1,
      new_version: version,
    })
    save()
    return getRun(id)
  },
}

function assetUrl(name: string | undefined): string {
  const url = name ? assetUrls[`./assets/${name}`] : undefined
  if (!url) throw new Error("Unknown sample artifact.")
  return url
}

export function demoCaseArtifactUrl(
  caseId: string,
  evidenceId: string
): string {
  return assetUrl(assetNames[caseId]?.[evidenceId])
}

export function demoRunArtifactUrl(id: string, name: string): string {
  const run = getRun(id)
  if (!run.artifacts.some((item) => item.name === name))
    throw new Error("Unknown sample artifact.")
  return assetUrl(name)
}

export function demoJobPreviewUrl(id: string, revision: number): string {
  const run = requireSample(id)
  if (revision !== 1) throw new Error("Unknown sample preview.")
  const page = run.source_case!.pages[0]
  return demoCaseArtifactUrl(run.source_case_id!, page.screenshot_evidence_id!)
}

export function demoExportUrl(
  id: string,
  extension: "md" | "json" | "zip"
): string {
  if (extension === "zip")
    throw new Error("The demo supports Markdown and JSON exports.")
  const key = `${id}:${extension}`
  const cached = exports.get(key)
  if (cached) return cached
  const run = getRun(id)
  const payload = {
    demo: true,
    limitation: fixtures.limitation,
    session_only: true,
    run,
  }
  const content =
    extension === "json"
      ? JSON.stringify(payload, null, 2)
      : [
          "# HAWK-EYE sample report",
          "",
          fixtures.limitation,
          "",
          "Reviews are local to this browser session.",
          "",
          `Seed: ${run.seed_url}`,
          `Capture: ${run.capture_adequacy}`,
          `Review: ${run.current_assertion_status ?? "Not applicable"}`,
          "",
          "## Sample observations",
          "",
          ...run.source_case!.observations.map(
            (item) =>
              `- ${item.display_value} (source: ${item.source_artifact_id})`
          ),
          "",
          "## Session reviews",
          "",
          ...(run.reviews ?? []).map(
            (item) => `- ${item.outcome}: ${item.reason}`
          ),
          "",
        ].join("\n")
  const url = URL.createObjectURL(
    new Blob([content], {
      type: extension === "json" ? "application/json" : "text/markdown",
    })
  )
  exports.set(key, url)
  return url
}

export {
  demoApi as api,
  demoCaseArtifactUrl as caseArtifactUrl,
  demoRunArtifactUrl as runArtifactUrl,
  demoJobPreviewUrl as jobPreviewUrl,
  demoExportUrl as runExportUrl,
}
