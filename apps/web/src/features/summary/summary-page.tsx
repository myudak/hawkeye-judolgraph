import {
  Archive,
  ArrowLeft,
  Binoculars,
  Browser,
  CheckCircle,
  ClockCounterClockwise,
  Code,
  DownloadSimple,
  File,
  FileJs,
  FileMd,
  Flag,
  Globe,
  Printer,
  ShieldCheck,
  Star,
  Warning,
} from "@phosphor-icons/react"
import { useQuery } from "@tanstack/react-query"
import { useNavigate, useParams } from "react-router-dom"

import { api, runExportUrl } from "@/api/client"
import type { CaseDetails, EvidenceSource, IndicatorSummary } from "@/api/types"
import { AppHeader } from "@/components/app-header"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { exactTime, formatTime, hostnameFrom, titleCase } from "@/lib/format"

const EMPTY_INDICATORS: IndicatorSummary = {
  indicator_count: 0,
  reviewed_observation_count: 0,
  category_counts: {},
  osint_counts: {},
  classifications: [],
}

function sourceCase(source: EvidenceSource): CaseDetails | undefined {
  return source.kind === "case"
    ? source.details
    : (source.details.source_case ?? undefined)
}

function SummaryMetric({
  icon: Icon,
  value,
  label,
}: {
  icon: typeof Browser
  value: number
  label: string
}) {
  return (
    <article className="report-metric">
      <Icon weight="duotone" />
      <strong>{value}</strong>
      <span>{label}</span>
    </article>
  )
}

function ReportCard({
  title,
  detail,
  icon: Icon,
  children,
}: {
  title: string
  detail: string
  icon: typeof Browser
  children: React.ReactNode
}) {
  return (
    <Card className="report-card">
      <CardHeader>
        <div>
          <Icon weight="duotone" />
          <span>
            <CardTitle>{title}</CardTitle>
            <small>{detail}</small>
          </span>
        </div>
      </CardHeader>
      <CardContent>{children}</CardContent>
    </Card>
  )
}

function ReportRows({
  rows,
  empty,
}: {
  rows: Array<[string, string]>
  empty: string
}) {
  if (!rows.length) return <p className="report-empty">{empty}</p>
  return (
    <div className="report-rows">
      {rows.map(([label, value], index) => (
        <div key={`${label}:${index}`}>
          <span>{label}</span>
          <b>{value}</b>
        </div>
      ))}
    </div>
  )
}

export function SummaryPage() {
  const { kind, id } = useParams<{ kind: "case" | "run"; id: string }>()
  const navigate = useNavigate()
  const sourceQuery = useQuery({
    queryKey: [kind, id],
    queryFn: async (): Promise<EvidenceSource> => {
      if (!id || (kind !== "case" && kind !== "run"))
        throw new Error("Invalid report route")
      return kind === "case"
        ? { kind, id, details: await api.getCase(id) }
        : { kind, id, details: await api.getRun(id) }
    },
    enabled: Boolean(id && (kind === "case" || kind === "run")),
  })

  if (sourceQuery.isError) {
    return (
      <div className="app-page summary-page">
        <AppHeader context="summary" />
        <main className="workspace-error">
          <Warning weight="duotone" />
          <h1>Summary unavailable</h1>
          <p>{sourceQuery.error.message}</p>
          <Button onClick={() => navigate("/")}>Return to cases</Button>
        </main>
      </div>
    )
  }
  if (sourceQuery.isPending || !sourceQuery.data) {
    return (
      <div className="app-page summary-page">
        <AppHeader context="summary" />
        <main className="report-loading">
          <Skeleton className="h-24 w-full" />
          <Skeleton className="h-80 w-full" />
        </main>
      </div>
    )
  }

  const source = sourceQuery.data
  const details = source.details
  const run = source.kind === "run" ? source.details : undefined
  const standaloneCase = source.kind === "case" ? source.details : undefined
  const captured = sourceCase(source)
  const events = run?.events ?? []
  const artifacts = run?.artifacts ?? standaloneCase?.evidence ?? []
  const assertions = run
    ? run.assertions?.length
      ? run.assertions
      : run.assertion
        ? [run.assertion]
        : []
    : []
  const pendingLeads = run?.pending_leads ?? []
  const indicators =
    details.gambling_indicators ??
    captured?.gambling_indicators ??
    EMPTY_INDICATORS
  const host = hostnameFrom(
    run
      ? run.seed_url || captured?.final_url_display || run.case_id
      : standaloneCase?.final_url_display || standaloneCase?.seed_url_display
  )
  const pages = captured?.pages ?? []
  const observations = captured?.observations ?? []
  const pendingReview = run
    ? (run.pending_review_count ?? 0) + pendingLeads.length
    : 0

  return (
    <div className="app-page summary-page">
      <AppHeader
        context="summary"
        currentValue={`${source.kind}:${source.id}`}
      />
      <main className="report-main">
        <header className="report-heading">
          <div>
            <p className="eyebrow">
              <Flag weight="fill" /> CASE SUMMARY
            </p>
            <h1>Investigation summary</h1>
            <strong>{host}</strong>
            <p>
              Human-readable projection of verified artifacts, persisted events,
              and append-only review state.
            </p>
          </div>
          <Button
            variant="outline"
            onClick={() => navigate(`/workspace/${source.kind}/${source.id}`)}
          >
            <ArrowLeft />
            Back to graph
          </Button>
        </header>

        <section className="report-hero">
          <div className="report-metric-grid">
            <SummaryMetric
              icon={Browser}
              value={pages.length}
              label="Pages captured"
            />
            <SummaryMetric
              icon={Binoculars}
              value={observations.length}
              label="Public observations"
            />
            <SummaryMetric
              icon={Star}
              value={assertions.length + pendingLeads.length}
              label="Candidate relations"
            />
            <SummaryMetric
              icon={ShieldCheck}
              value={pendingReview}
              label="Pending review"
            />
            <SummaryMetric
              icon={Warning}
              value={indicators.indicator_count || 0}
              label="Judol indicators"
            />
          </div>
          <div className="report-truth">
            <ShieldCheck weight="duotone" />
            <span>
              <b>Interpretation boundary</b> Indicators are evidence-item
              counts. Candidates are not ownership claims. Similarity is not
              probability.
            </span>
          </div>
        </section>

        <section className="report-grid">
          <div className="report-column">
            <ReportCard
              title="Scope and limitations"
              detail="Truthful operating envelope"
              icon={Globe}
            >
              <ReportRows
                empty="No scope record."
                rows={[
                  [
                    "Seed",
                    run?.seed_url ||
                      standaloneCase?.seed_url_display ||
                      "Not recorded",
                  ],
                  [
                    "Collection",
                    run ? titleCase(run.source_kind) : "Deterministic capture",
                  ],
                  [
                    "Agent stop",
                    run
                      ? titleCase(run.agent_stop_reason || "not applicable")
                      : "Not applicable",
                  ],
                  ["Safety", "Public, read-only, policy gated"],
                  ["Inference", "Candidates require human review"],
                ]}
              />
            </ReportCard>

            <ReportCard
              title="Collected pages"
              detail={`${pages.length} saved page records`}
              icon={Browser}
            >
              <ReportRows
                empty="No collected page list is attached."
                rows={pages.map((page) => [
                  page.final_url_display || page.id,
                  titleCase(page.capture_adequacy || page.state || "captured"),
                ])}
              />
            </ReportCard>

            <ReportCard
              title="Public OSINT evidence profile"
              detail={`${indicators.reviewed_observation_count || 0} classifications`}
              icon={Binoculars}
            >
              <ReportRows
                empty="No semantic OSINT observations were available."
                rows={Object.entries(indicators.osint_counts ?? {}).map(
                  ([category, count]) => [
                    titleCase(category),
                    `${count} evidence item${count === 1 ? "" : "s"}`,
                  ]
                )}
              />
            </ReportCard>

            <ReportCard
              title="Judol indicator evidence"
              detail={`${indicators.indicator_count || 0} counted · no percentage`}
              icon={Warning}
            >
              <ReportRows
                empty="No controlled judol indicator matched the captured public evidence."
                rows={(indicators.classifications ?? [])
                  .filter((item) => item.label === "indicator")
                  .map((item) => [
                    `${item.display_value || item.observation_id} · ${item.observation_id}`,
                    `${titleCase(item.category)} · ${item.matched_terms?.join(", ") || "context"}`,
                  ])}
              />
            </ReportCard>

            <ReportCard
              title="Candidate relationships"
              detail={`${assertions.length} assertions · ${pendingLeads.length} approval leads`}
              icon={Star}
            >
              <ReportRows
                empty="No candidate relationship or lead was observed."
                rows={[
                  ...assertions.map((item): [string, string] => [
                    `${item.subject || item.subject_node_id || "subject"} → ${item.object || item.object_node_id || "candidate"}`,
                    titleCase(item.assertion_type || "candidate"),
                  ]),
                  ...pendingLeads.map((item): [string, string] => [
                    item.url || item.lead_id || "Pending lead",
                    "Waiting for approval",
                  ]),
                ]}
              />
            </ReportCard>
          </div>

          <div className="report-column">
            <ReportCard
              title="Export and print"
              detail="Human and machine-readable"
              icon={DownloadSimple}
            >
              <div className="export-actions">
                {run ? (
                  <>
                    <a href={runExportUrl(run.workspace_id, "md")} download>
                      <FileMd weight="duotone" />
                      <span>Markdown</span>
                      <small>.md report</small>
                    </a>
                    <a href={runExportUrl(run.workspace_id, "json")} download>
                      <FileJs weight="duotone" />
                      <span>JSON</span>
                      <small>Structured case</small>
                    </a>
                    <a href={runExportUrl(run.workspace_id, "zip")} download>
                      <Archive weight="duotone" />
                      <span>Case archive</span>
                      <small>.zip package</small>
                    </a>
                  </>
                ) : null}
                <button type="button" onClick={() => window.print()}>
                  <Printer weight="duotone" />
                  <span>Print summary</span>
                  <small>Browser print</small>
                </button>
              </div>
            </ReportCard>

            <ReportCard
              title="Event chronology"
              detail={`${events.length} persisted events`}
              icon={ClockCounterClockwise}
            >
              {events.length ? (
                <div className="chronology">
                  {events.slice(0, 90).map((event) => (
                    <article key={event.event_id}>
                      <time title={exactTime(event.occurred_at)}>
                        {formatTime(event.occurred_at)}
                      </time>
                      <span>
                        <i />
                        <b>{titleCase(event.kind)}</b>
                        <small>{event.event_id}</small>
                      </span>
                    </article>
                  ))}
                </div>
              ) : (
                <p className="report-empty">
                  This deterministic case predates the append-only event
                  runtime.
                </p>
              )}
            </ReportCard>

            <ReportCard
              title="Artifact manifest"
              detail={`${artifacts.length} integrity-tracked files`}
              icon={File}
            >
              <ReportRows
                empty="No artifact manifest is attached."
                rows={artifacts.map((item) => [
                  "name" in item ? item.name : item.id,
                  String(
                    "bytes" in item
                      ? item.bytes || item.type || "saved"
                      : item.type
                  ),
                ])}
              />
            </ReportCard>

            <ReportCard
              title="Review posture"
              detail="No implicit relationship upgrades"
              icon={CheckCircle}
            >
              <div className="review-posture">
                <Badge className="status-badge status-success">
                  Verified artifacts
                </Badge>
                <Badge className="status-badge status-warning">
                  {pendingReview} pending decisions
                </Badge>
                <p>
                  Only persisted human review can emphasize a relationship edge.
                  Replaying or exporting the case does not change evidence
                  truth.
                </p>
              </div>
            </ReportCard>

            <ReportCard
              title="Technical envelope"
              detail={details.case_id}
              icon={Code}
            >
              <ReportRows
                empty="No technical details."
                rows={[
                  ["Case ID", details.case_id],
                  ["Kind", source.kind],
                  ["Artifacts", String(artifacts.length)],
                  ["Events", String(events.length)],
                ]}
              />
            </ReportCard>
          </div>
        </section>
      </main>
    </div>
  )
}
