import {
  ArrowRight,
  Binoculars,
  Browser,
  Check,
  Clock,
  Code,
  CursorClick,
  Database,
  FileText,
  FlagCheckered,
  Graph,
  HardDrives,
  ImageSquare,
  MagnifyingGlass,
  Pulse,
  ShieldCheck,
  Sparkle,
  SpinnerGap,
  Warning,
} from "@phosphor-icons/react"
import { useQuery } from "@tanstack/react-query"
import { useEffect, useMemo, useState } from "react"
import { useNavigate, useParams } from "react-router-dom"

import { api, jobPreviewUrl } from "@/api/client"
import type { InvestigationJob, JobPreview } from "@/api/types"
import { AppHeader } from "@/components/app-header"
import { HawkMark } from "@/components/brand-mark"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { ScrollArea } from "@/components/ui/scroll-area"
import {
  formatElapsed,
  formatTime,
  hostnameFrom,
  titleCase,
} from "@/lib/format"
import { cn } from "@/lib/utils"

const stageGroups = [
  {
    label: "Validate target",
    stages: ["queued", "validating_seed", "launching_browser"],
    icon: ShieldCheck,
  },
  {
    label: "Capture pages",
    stages: ["initializing_case", "capturing_page"],
    icon: Browser,
  },
  {
    label: "Preserve & extract",
    stages: [
      "preserving_artifacts",
      "page_preview_ready",
      "running_ocr",
      "extracting_evidence",
      "page_completed",
      "generating_candidates",
      "finalizing_case",
    ],
    icon: FileText,
  },
  {
    label: "Bounded investigation",
    stages: [
      "verifying_evidence",
      "evidence_verified",
      "running_agent",
      "agent_focus_ready",
      "interaction_preview_ready",
      "agent_observations_ready",
      "agent_focus_blocked",
    ],
    icon: MagnifyingGlass,
  },
  {
    label: "Classify & graph",
    stages: ["classifying_indicators", "building_graph"],
    icon: Graph,
  },
  { label: "Finalize case", stages: ["completed"], icon: FlagCheckered },
]

const stageCopy: Record<string, [string, string]> = {
  queued: [
    "Preparing isolated workspace",
    "A single local investigation slot has been reserved.",
  ],
  validating_seed: [
    "Validating public destination",
    "Checking scheme, destination, and read-only collection policy.",
  ],
  launching_browser: [
    "Launching isolated browser",
    "Starting a killable browser worker with a hard wall-clock boundary.",
  ],
  initializing_case: [
    "Creating immutable case record",
    "Recording scope, page budget, depth, and the normalized seed.",
  ],
  capturing_page: [
    "Capturing rendered page",
    "Waiting for visible render stability and collecting same-site public navigation.",
  ],
  preserving_artifacts: [
    "Preserving source artifacts",
    "Saving initial, canonical, and full-page screenshots with rendered HTML and response facts.",
  ],
  page_preview_ready: [
    "Canonical preview ready",
    "A real viewport screenshot has been persisted and is available as a transient preview.",
  ],
  running_ocr: [
    "Checking screenshot text",
    "Running bounded local OCR as supplemental evidence; OCR never replaces source artifacts.",
  ],
  extracting_evidence: [
    "Extracting public OSINT evidence",
    "Linking public contacts, offers, payments, destinations, and claims to page evidence.",
  ],
  page_completed: [
    "Page evidence committed",
    "The current page record and evidence references are now persisted.",
  ],
  generating_candidates: [
    "Generating reviewable leads",
    "Comparing verified evidence without treating similarity as ownership probability.",
  ],
  finalizing_case: [
    "Finalizing case package",
    "Writing the manifest and truthful capture limitations.",
  ],
  verifying_evidence: [
    "Re-verifying saved artifacts",
    "Checking the completed case package before the agent can inspect it.",
  ],
  evidence_verified: [
    "Case evidence verified",
    "The manifest and captured artifact hashes passed local verification.",
  ],
  running_agent: [
    "Running policy-gated exploration",
    "Planning safe public interactions with deterministic fallback and recorded tool events.",
  ],
  agent_focus_ready: [
    "Agent selected a safe control",
    "The server re-validated the reference and recorded its real viewport position.",
  ],
  interaction_preview_ready: [
    "Public interaction captured",
    "The resulting read-only page state and screenshot have been persisted.",
  ],
  agent_observations_ready: [
    "Interaction evidence extracted",
    "Visible public observations were checked after the safe action.",
  ],
  agent_focus_blocked: [
    "Safe action stopped",
    "The policy-gated action did not complete; no completion is implied.",
  ],
  classifying_indicators: [
    "Classifying judol indicators",
    "Counting evidence-backed text/entity indicators without percentages or verdicts.",
  ],
  building_graph: [
    "Building event-sourced graph",
    "Reducing persisted pages, observations, leads, and actions into the investigation view.",
  ],
  completed: [
    "Investigation ready",
    "The saved graph, screenshots, evidence, and timeline are ready for review.",
  ],
  failed: [
    "Investigation stopped safely",
    "The failure boundary was recorded; no result is presented as a completed capture.",
  ],
}

function detailNumber(job: InvestigationJob, key: string): number | null {
  const value = job.detail?.[key]
  return typeof value === "number" && Number.isFinite(value) ? value : null
}

function currentGroup(job: InvestigationJob): number {
  if (job.stage === "failed") {
    return Math.max(
      0,
      ...(job.history ?? []).map((item) =>
        stageGroups.findIndex((group) => group.stages.includes(item.stage))
      )
    )
  }
  return stageGroups.findIndex((group) => group.stages.includes(job.stage))
}

function stageIcon(stage: string) {
  if (stage.includes("capture") || stage.includes("artifact")) return Browser
  if (stage.includes("extract") || stage.includes("ocr")) return FileText
  if (stage.includes("agent") || stage.includes("candidate"))
    return MagnifyingGlass
  if (stage.includes("graph") || stage.includes("classif")) return Graph
  if (stage === "failed") return Warning
  return Check
}

function previewTitle(preview: JobPreview): string {
  if (preview.kind === "agent_before") return "Before safe action"
  if (preview.kind === "agent_after") return "After safe action"
  return preview.page_id.replace("page-", "Page ")
}

interface ProcessedSite {
  title: string
  hostname: string
}

function processedSite(job?: InvestigationJob): ProcessedSite {
  const sourceCase = job?.result?.source_case
  const url =
    job?.target?.final_url ||
    job?.visual_state?.latest_preview?.url ||
    sourceCase?.final_url_display ||
    job?.target?.seed_url ||
    job?.result?.seed_url ||
    ""
  const hostname = url ? hostnameFrom(url) : "Preparing target"
  const title =
    job?.target?.page_title?.trim() ||
    sourceCase?.page_title?.trim() ||
    hostname

  return { title, hostname }
}

function ScanVisual({
  job,
  site,
}: {
  job?: InvestigationJob
  site: ProcessedSite
}) {
  const previews = job?.visual_state?.previews ?? []
  const latest = job?.visual_state?.latest_preview
  const focus = job?.visual_state?.agent_focus
  const [selectedRevision, setSelectedRevision] = useState<number | null>(null)

  const selected =
    previews.find((item) => item.revision === selectedRevision) ?? latest
  const targetBox = focus?.target_bbox
  const viewportWidth = focus?.viewport?.width ?? 0
  const viewportHeight = focus?.viewport?.height ?? 0
  const showTarget = Boolean(
    selected?.kind === "agent_before" &&
    focus?.target_preview_revision === selected.revision &&
    targetBox &&
    viewportWidth > 0 &&
    viewportHeight > 0
  )
  const targetStyle =
    showTarget && targetBox
      ? {
          left: `${(targetBox.x / viewportWidth) * 100}%`,
          top: `${(targetBox.y / viewportHeight) * 100}%`,
          width: `${(targetBox.width / viewportWidth) * 100}%`,
          height: `${(targetBox.height / viewportHeight) * 100}%`,
        }
      : undefined

  return (
    <div
      className="scan-preview-panel"
      aria-busy={job?.status === "queued" || job?.status === "running"}
    >
      {selected ? (
        <>
          <header className="preview-header">
            <span>
              <ImageSquare weight="duotone" />
              <b>{previewTitle(selected)}</b>
            </span>
            <Badge
              className={cn(
                "preview-verification",
                selected.verification === "verified" && "status-success",
                selected.verification === "persisted" && "status-cyan"
              )}
            >
              {selected.verification === "verified"
                ? "VERIFIED EVIDENCE"
                : selected.verification === "persisted"
                  ? "PERSISTED ACTION"
                  : "PREVIEW · VERIFICATION PENDING"}
            </Badge>
            {selected.revision !== latest?.revision ? (
              <button
                className="preview-follow"
                type="button"
                onClick={() => setSelectedRevision(null)}
              >
                Follow latest
              </button>
            ) : null}
          </header>
          <div
            className="preview-viewport"
            style={{
              aspectRatio:
                selected.width && selected.height
                  ? `${selected.width} / ${selected.height}`
                  : "1440 / 1024",
            }}
          >
            <img
              key={selected.revision}
              src={jobPreviewUrl(job!.job_id, selected.revision)}
              alt={`Captured public page preview: ${previewTitle(selected)}`}
              decoding="async"
            />
            {job?.status === "running" ? (
              <span className="preview-shimmer" aria-hidden="true" />
            ) : null}
            {job?.status === "running" ? (
              <span className="preview-scanline" aria-hidden="true" />
            ) : null}
            {targetStyle ? (
              <span className="agent-target" style={targetStyle}>
                <span className="agent-cursor">
                  <CursorClick weight="fill" />
                </span>
              </span>
            ) : null}
          </div>
          <div className="preview-caption" aria-live="polite">
            <span>
              <i
                className={cn(
                  "live-dot",
                  job?.status !== "running" && "live-dot-static"
                )}
              />
              {selected.url || "Captured public page"}
            </span>
            <small>{formatTime(selected.captured_at)}</small>
          </div>
          {focus ? (
            <div className={cn("agent-focus-card", `focus-${focus.status}`)}>
              <span>
                <CursorClick weight="duotone" />
              </span>
              <div>
                <b>
                  {focus.status === "selected"
                    ? "Agent selected a safe public control"
                    : focus.status === "evidence_extracted"
                      ? (focus.added_observation_count ?? 0) > 0
                        ? "New public observations extracted"
                        : "Post-action extraction completed"
                      : focus.status === "blocked"
                        ? "Safe action stopped"
                        : "Read-only action completed"}
                </b>
                <p>
                  {focus.label || "Public information control"}
                  {focus.status === "blocked" && focus.reason
                    ? ` · ${focus.reason}`
                    : (focus.added_observation_count ?? 0) > 0
                      ? ` · ${focus.added_observation_count} new observations`
                      : focus.status === "evidence_extracted"
                        ? " · no new observations"
                        : ""}
                </p>
                <small>{focus.tool_name || "Policy-gated tool"}</small>
              </div>
            </div>
          ) : null}
          {previews.length > 1 ? (
            <div
              className="preview-thumbnails"
              role="group"
              aria-label="Captured preview states"
            >
              {previews.slice(-6).map((preview) => (
                <button
                  key={preview.revision}
                  type="button"
                  className={cn(
                    preview.revision === selected.revision && "preview-selected"
                  )}
                  onClick={() => setSelectedRevision(preview.revision)}
                  aria-label={`Show ${previewTitle(preview)}`}
                  aria-pressed={preview.revision === selected.revision}
                >
                  <img
                    src={jobPreviewUrl(job!.job_id, preview.revision, true)}
                    alt=""
                    loading="lazy"
                    decoding="async"
                  />
                  <span>{previewTitle(preview)}</span>
                </button>
              ))}
            </div>
          ) : null}
        </>
      ) : (
        <div className="preview-waiting">
          <div className="scan-radar" aria-hidden="true">
            <span className="radar-ring radar-ring-one" />
            <span className="radar-ring radar-ring-two" />
            <span className="radar-ring radar-ring-three" />
            <span className="radar-axis radar-axis-x" />
            <span className="radar-axis radar-axis-y" />
            <span className="radar-sweep" />
            <span className="radar-ping ping-one" />
            <span className="radar-ping ping-two" />
            <span className="radar-core">
              <HawkMark variant="radar" />
            </span>
          </div>
          <div className="preview-target-identity" aria-live="polite">
            <span>Website being processed</span>
            <strong>{site.title}</strong>
            {site.hostname !== site.title ? (
              <small>{site.hostname}</small>
            ) : null}
          </div>
          <b>
            {job?.status === "failed"
              ? "No preview was preserved"
              : "Waiting for the first persisted frame"}
          </b>
          <p>
            {job?.status === "failed"
              ? "Capture stopped before a valid screenshot became available."
              : "The preview appears after a real screenshot has been safely written."}
          </p>
        </div>
      )}
      <Badge
        className={cn(
          "scan-state-badge",
          job?.status === "failed" && "status-danger",
          job?.status === "completed" && "status-success"
        )}
      >
        <span
          className={cn(
            "live-dot",
            job?.status !== "running" && "live-dot-static"
          )}
        />
        {job?.status === "failed"
          ? "CAPTURE STOPPED"
          : job?.status === "completed"
            ? "EVIDENCE SAVED"
            : "INVESTIGATION ACTIVE"}
      </Badge>
    </div>
  )
}

export function ScanPage() {
  const { jobId } = useParams<{ jobId: string }>()
  const navigate = useNavigate()
  const [now, setNow] = useState(() => Date.now())
  const jobQuery = useQuery({
    queryKey: ["job", jobId],
    queryFn: () => api.getJob(jobId || ""),
    enabled: Boolean(jobId),
    refetchInterval: (query) =>
      ["queued", "running"].includes(query.state.data?.status ?? "")
        ? 650
        : false,
    retry: (count, error) =>
      count < 2 && !("status" in error && error.status === 404),
  })
  const jobIsActive = jobQuery.data?.status
    ? ["queued", "running"].includes(jobQuery.data.status)
    : false

  useEffect(() => {
    if (!jobIsActive) return
    const timer = window.setInterval(() => setNow(Date.now()), 1_000)
    return () => window.clearInterval(timer)
  }, [jobIsActive])

  const job = jobQuery.data
  const site = processedSite(job)
  const elapsedAt = jobIsActive
    ? now
    : job?.updated_at
      ? new Date(job.updated_at).getTime()
      : now
  const groupIndex = job ? currentGroup(job) : 0
  const [phaseTitle, phaseCopy] = stageCopy[job?.stage ?? "queued"] ?? [
    titleCase(job?.stage),
    "Recording the current bounded operation.",
  ]
  const pages =
    job?.result?.source_case?.pages?.length ??
    (job?.history ?? []).filter((item) => item.stage === "preserving_artifacts")
      .length
  const evidence =
    job?.result?.source_case?.observations?.length ??
    detailNumber(
      job ?? ({ detail: {} } as InvestigationJob),
      "observation_count"
    )
  const queue =
    job?.status === "completed"
      ? 0
      : detailNumber(
          job ?? ({ detail: {} } as InvestigationJob),
          "queued_pages"
        )
  const workspaceId = job?.result?.workspace_id
  const history = useMemo(() => (job?.history ?? []).slice(-30), [job?.history])

  if (jobQuery.isError) {
    return (
      <div className="app-page scan-page">
        <AppHeader context="scan" />
        <main className="scan-error">
          <Warning weight="duotone" />
          <h1>Investigation state unavailable</h1>
          <p>{jobQuery.error.message}</p>
          <Button onClick={() => navigate("/")}>Return to cases</Button>
        </main>
      </div>
    )
  }

  return (
    <div className="app-page scan-page">
      <AppHeader context="scan" />
      <main className="scan-main-page">
        <section
          className={cn(
            "scan-console",
            job?.status === "failed" && "scan-console-failed",
            job?.status === "completed" && "scan-console-complete"
          )}
        >
          <ScanVisual job={job} site={site} />

          <div className="scan-progress-panel">
            <div className="scan-target-summary" aria-live="polite">
              <span className="scan-target-icon">
                <Browser weight="duotone" />
              </span>
              <div>
                <span>Website being processed</span>
                <strong>{site.title}</strong>
                {site.hostname !== site.title ? (
                  <small>{site.hostname}</small>
                ) : null}
              </div>
            </div>
            <header className="scan-phase-heading">
              <div>
                <p className="eyebrow">CURRENT PHASE</p>
                <h1 aria-live="polite">{phaseTitle}</h1>
                <p>{job?.error || phaseCopy}</p>
              </div>
              <span className="elapsed-clock">
                <Clock weight="duotone" />
                {formatElapsed(job?.started_at, elapsedAt)}
              </span>
            </header>

            <div className="scan-metrics">
              <article>
                <span>
                  <Browser weight="duotone" />
                </span>
                <strong>{pages}</strong>
                <p>Pages captured</p>
                <small>{queue ?? "—"} queued</small>
              </article>
              <article>
                <span>
                  <Binoculars weight="duotone" />
                </span>
                <strong>{evidence ?? "—"}</strong>
                <p>Evidence observations</p>
                <small>Deterministic extractors</small>
              </article>
              <article>
                <span>
                  <Clock weight="duotone" />
                </span>
                <strong>{formatElapsed(job?.started_at, elapsedAt)}</strong>
                <p>Elapsed time</p>
                <small>Bounded collector and agent timing</small>
              </article>
              <article>
                <span>
                  <Database weight="duotone" />
                </span>
                <strong>
                  {groupIndex + 1} / {stageGroups.length}
                </strong>
                <p>Pipeline stage</p>
                <small>{job?.stage ? titleCase(job.stage) : "Loading"}</small>
              </article>
            </div>

            <ol className="pipeline-stages">
              {stageGroups.map((group, index) => {
                const Icon = group.icon
                const reached =
                  index < groupIndex || job?.status === "completed"
                const active = index === groupIndex && jobIsActive
                const failed = index === groupIndex && job?.status === "failed"
                return (
                  <li
                    key={group.label}
                    className={cn(
                      reached && "stage-reached",
                      active && "stage-active",
                      failed && "stage-failed"
                    )}
                    aria-current={active || failed ? "step" : undefined}
                  >
                    <span className="stage-index">
                      {reached ? <Check weight="bold" /> : index + 1}
                    </span>
                    <Icon weight="duotone" />
                    <strong>{group.label}</strong>
                    <small>
                      {failed
                        ? "Stopped"
                        : reached
                          ? "Completed"
                          : active
                            ? "In progress"
                            : "Pending"}
                    </small>
                  </li>
                )
              })}
            </ol>

            {job?.status === "completed" && workspaceId ? (
              <Button
                className="open-workspace-button"
                size="lg"
                onClick={() => navigate(`/workspace/run/${workspaceId}`)}
              >
                Open evidence workspace <ArrowRight weight="bold" />
              </Button>
            ) : null}
            {job?.status === "failed" ? (
              <Button
                className="open-workspace-button"
                variant="outline"
                size="lg"
                onClick={() => navigate("/")}
              >
                Return to investigation form
              </Button>
            ) : null}
          </div>
        </section>

        <section className="activity-console">
          <header>
            <div>
              <Pulse weight="fill" />
              <span>LIVE ACTIVITY STREAM</span>
            </div>
            <Badge variant="outline" aria-live="polite">
              <span
                className={cn("live-dot", !jobIsActive && "live-dot-static")}
              />{" "}
              {job?.status === "completed"
                ? "Captured"
                : job?.status === "failed"
                  ? "Stopped"
                  : "Live"}
            </Badge>
          </header>
          <ScrollArea className="activity-scroll">
            <div className="activity-list" aria-live="polite">
              {history.length ? (
                history.map((entry, index) => {
                  const Icon = stageIcon(entry.stage)
                  const [label, copy] = stageCopy[entry.stage] ?? [
                    titleCase(entry.stage),
                    "Persisted bounded stage transition.",
                  ]
                  return (
                    <article
                      key={`${entry.stage}:${entry.at}:${index}`}
                      className="activity-row"
                      style={{
                        animationDelay: `${Math.min(index * 25, 200)}ms`,
                      }}
                    >
                      <span className="activity-icon">
                        <Icon weight="duotone" />
                      </span>
                      <strong>{label}</strong>
                      <p>{copy}</p>
                      <time dateTime={entry.at}>{formatTime(entry.at)}</time>
                    </article>
                  )
                })
              ) : (
                <article className="activity-empty">
                  <SpinnerGap className="animate-spin" /> Waiting for the first
                  persisted stage…
                </article>
              )}
            </div>
          </ScrollArea>
        </section>

        <section className="technical-strip">
          <span className="technical-label">
            <Code weight="duotone" /> TECHNICAL PROGRESS
          </span>
          <div>
            {history.slice(-8).map((entry, index) => (
              <span key={`${entry.stage}:${index}`}>
                <i /> {titleCase(entry.stage)}{" "}
                <time>{formatTime(entry.at)}</time>
              </span>
            ))}
            {!history.length ? (
              <span>
                <i /> Browser worker pending
              </span>
            ) : null}
          </div>
          <HardDrives weight="duotone" />
        </section>

        <aside className="scan-boundary">
          <ShieldCheck weight="duotone" />
          <span>
            <b>Evidence boundary active.</b> HAWK-EYE will not sign in, submit
            forms, message contacts, purchase, or bypass access controls.
          </span>
          <Sparkle weight="duotone" />
        </aside>
      </main>
    </div>
  )
}
