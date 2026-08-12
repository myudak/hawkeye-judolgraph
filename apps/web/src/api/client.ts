import type {
  CapabilityStatus,
  CaseDetails,
  CaseListItem,
  InvestigationJob,
  RunDetails,
  RunListItem,
  DesktopSettings,
  DesktopSettingsUpdate,
} from "@/api/types"

export class ApiError extends Error {
  readonly status: number

  constructor(message: string, status: number) {
    super(message)
    this.name = "ApiError"
    this.status = status
  }
}

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    credentials: "same-origin",
    cache: "no-store",
    ...init,
  })
  if (!response.ok) {
    let message = `Request failed (${response.status})`
    try {
      const payload = (await response.json()) as {
        error?: string
        detail?: string
      }
      message = payload.error ?? payload.detail ?? message
    } catch {
      // The bounded HTTP status remains the failure detail.
    }
    throw new ApiError(message, response.status)
  }
  return response.json() as Promise<T>
}

function postJson<T>(path: string, payload: unknown): Promise<T> {
  return requestJson<T>(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  })
}

function putJson<T>(path: string, payload: unknown): Promise<T> {
  return requestJson<T>(path, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  })
}

export const api = {
  listCases: () => requestJson<{ cases: CaseListItem[] }>("/api/cases"),
  listRuns: () => requestJson<{ runs: RunListItem[] }>("/api/mvp/runs"),
  capability: () => requestJson<CapabilityStatus>("/api/mvp/capabilities"),
  settings: () => requestJson<DesktopSettings>("/api/settings"),
  updateSettings: (payload: DesktopSettingsUpdate) =>
    putJson<DesktopSettings>("/api/settings", payload),
  activeJob: () =>
    requestJson<{ job: InvestigationJob | null }>(
      "/api/investigation-jobs/active"
    ),
  getJob: (jobId: string) =>
    requestJson<InvestigationJob>(
      `/api/investigation-jobs/${encodeURIComponent(jobId)}`
    ),
  startJob: (payload: {
    seed_url: string
    investigation_name: string
    investigation_mode: "guided" | "capture_only"
  }) => postJson<InvestigationJob>("/api/investigation-jobs", payload),
  getCase: (caseId: string) =>
    requestJson<CaseDetails>(`/api/cases/${encodeURIComponent(caseId)}`),
  getRun: (workspaceId: string) =>
    requestJson<RunDetails>(`/api/mvp/runs/${encodeURIComponent(workspaceId)}`),
  createWalkthrough: () =>
    postJson<{ workspace_id: string }>("/api/mvp/runs", {
      scenario_id: "redirect-new-tab",
      collection_mode: "synthetic_fixture",
    }),
  approveCandidate: (workspaceId: string) =>
    postJson<unknown>(
      `/api/mvp/runs/${encodeURIComponent(workspaceId)}/approve`,
      {}
    ),
  appendReview: (
    workspaceId: string,
    payload: {
      assertion_id: string
      outcome: string
      reviewer_label: string
      reason: string
    }
  ) =>
    postJson<unknown>(
      `/api/mvp/runs/${encodeURIComponent(workspaceId)}/reviews`,
      payload
    ),
}

export function caseArtifactUrl(caseId: string, evidenceId: string): string {
  return `/api/cases/${encodeURIComponent(caseId)}/artifacts/${encodeURIComponent(evidenceId)}`
}

export function runArtifactUrl(workspaceId: string, name: string): string {
  return `/api/mvp/runs/${encodeURIComponent(workspaceId)}/artifacts/${encodeURIComponent(name)}`
}

export function jobPreviewUrl(
  jobId: string,
  revision: number,
  thumbnail = false
): string {
  const thumbnailQuery = thumbnail ? "&thumbnail=true" : ""
  return `/api/investigation-jobs/${encodeURIComponent(jobId)}/preview?revision=${encodeURIComponent(revision)}${thumbnailQuery}`
}

export function runExportUrl(
  workspaceId: string,
  extension: "md" | "json" | "zip"
): string {
  return `/api/mvp/runs/${encodeURIComponent(workspaceId)}/export.${extension}`
}
