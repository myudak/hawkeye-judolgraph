import {
  Binoculars,
  Browser,
  Check,
  FadersHorizontal,
  Robot,
  ShieldCheck,
  Star,
  WarningCircle,
} from "@phosphor-icons/react"

import type { CaseDetails, EvidenceSource, IndicatorSummary } from "@/api/types"
import { Badge } from "@/components/ui/badge"
import { ScrollArea } from "@/components/ui/scroll-area"
import {
  GRAPH_FILTERS,
  type GraphProjection,
  type VisualKind,
} from "@/lib/graph"
import { hostnameFrom, titleCase } from "@/lib/format"

const EMPTY_INDICATORS: IndicatorSummary = {
  status: "insufficient_evidence",
  indicator_count: 0,
  reviewed_observation_count: 0,
  category_counts: {},
  osint_counts: {},
  classifications: [],
  limitations: [],
}

function indicatorsFor(source: EvidenceSource): IndicatorSummary {
  return (
    source.details.gambling_indicators ??
    (source.kind === "run"
      ? source.details.source_case?.gambling_indicators
      : undefined) ??
    EMPTY_INDICATORS
  )
}

function sourceCaseFor(source: EvidenceSource): CaseDetails | undefined {
  return source.kind === "case"
    ? source.details
    : (source.details.source_case ?? undefined)
}

function statusTone(value?: string | null): string {
  if (!value) return "status-muted"
  if (
    [
      "adequate",
      "captured",
      "content",
      "verified",
      "recollected",
      "codex",
    ].includes(value)
  )
    return "status-success"
  if (["failed", "error", "rejected"].includes(value)) return "status-danger"
  return "status-warning"
}

function Metric({
  value,
  label,
  icon: Icon,
}: {
  value: number
  label: string
  icon: typeof Browser
}) {
  return (
    <article className="summary-metric">
      <Icon weight="duotone" />
      <strong>{value}</strong>
      <small>{label}</small>
    </article>
  )
}

export function CaseSummary({
  source,
  projection,
  filters,
  onToggleFilter,
}: {
  source: EvidenceSource
  projection: GraphProjection
  filters: ReadonlySet<VisualKind>
  onToggleFilter: (kind: VisualKind, enabled: boolean) => void
}) {
  const run = source.kind === "run" ? source.details : undefined
  const standaloneCase = source.kind === "case" ? source.details : undefined
  const sourceCase = sourceCaseFor(source)
  const indicators = indicatorsFor(source)
  const hostname = hostnameFrom(
    run
      ? run.seed_url || sourceCase?.final_url_display || run.case_id
      : standaloneCase?.final_url_display || standaloneCase?.seed_url_display
  )
  const pages =
    sourceCase?.pages?.length ??
    projection.nodes.filter((node) => node.presentation.visualKind === "page")
      .length
  const evidence = sourceCase?.observations?.length ?? 0
  const candidates = run
    ? (run.pending_leads?.length ?? 0) +
      (run.assertions?.length ?? (run.assertion ? 1 : 0))
    : (standaloneCase?.candidates?.length ?? 0)
  const actions = run
    ? Math.max(
        run.action_summary?.status === "completed" ? 1 : 0,
        run.events.filter((event) => event.kind === "tool.completed").length
      )
    : 0

  const statuses = run
    ? [
        run?.agent_mode,
        run?.capture_adequacy || sourceCase?.capture_adequacy,
        run?.extraction_tier || sourceCase?.extraction_tier,
        run?.lead_status,
      ]
    : [
        standaloneCase?.public_status,
        standaloneCase?.capture_adequacy,
        standaloneCase?.access_outcome,
      ]

  return (
    <aside className="case-summary-panel" aria-label="Case summary">
      <ScrollArea className="case-summary-scroll">
        <div className="case-summary-content">
          <header className="case-summary-hero">
            <span className="panel-label">CASE SUMMARY</span>
            <h1>{hostname}</h1>
            <p>
              {source.kind === "run"
                ? `Event-sourced investigation using ${run?.agent_mode === "codex" ? run.agent_model || "Codex" : "the deterministic safe fallback"}. Animation never creates evidence.`
                : "Verified public capture. Graph nodes are observations and destinations, not identity or ownership conclusions."}
            </p>
            <div className="status-row">
              {statuses.filter(Boolean).map((status) => (
                <Badge
                  key={status}
                  className={`status-badge ${statusTone(status)}`}
                >
                  {titleCase(status)}
                </Badge>
              ))}
            </div>
          </header>

          <section className="summary-section">
            <h2>
              <Binoculars weight="duotone" /> Investigation facts
            </h2>
            <div className="summary-metric-grid">
              <Metric value={pages} label="Captured pages" icon={Browser} />
              <Metric
                value={evidence}
                label="Semantic evidence"
                icon={Binoculars}
              />
              <Metric value={candidates} label="Reviewable leads" icon={Star} />
              <Metric value={actions} label="Safe agent actions" icon={Robot} />
              <Metric
                value={indicators.indicator_count || 0}
                label="Judol indicators"
                icon={WarningCircle}
              />
            </div>
          </section>

          <section className="summary-section indicator-boundary-card">
            <h2>
              <ShieldCheck weight="duotone" /> OSINT indicator boundary
            </h2>
            <strong>{indicators.indicator_count || 0} evidence items</strong>
            <p>
              Rule-classified public text/entity evidence. This is not a
              percentage, probability, legal conclusion, or operator
              attribution.
            </p>
            <div className="indicator-chip-list">
              {Object.entries(indicators.category_counts ?? {}).map(
                ([category, count]) => (
                  <Badge variant="outline" key={category}>
                    {titleCase(category)} · {count}
                  </Badge>
                )
              )}
            </div>
          </section>

          <section className="summary-section graph-filter-section">
            <h2>
              <FadersHorizontal weight="duotone" /> Graph filters
            </h2>
            <div className="graph-filter-list">
              {GRAPH_FILTERS.map((filter) => {
                const count = projection.nodes.filter(
                  (node) => node.presentation.visualKind === filter.key
                ).length
                const checked = filters.has(filter.key)
                return (
                  <label
                    key={filter.key}
                    className="graph-filter-row"
                    style={
                      { "--filter-color": filter.color } as React.CSSProperties
                    }
                  >
                    <input
                      type="checkbox"
                      checked={checked}
                      onChange={(event) =>
                        onToggleFilter(filter.key, event.target.checked)
                      }
                    />
                    <span className="graph-filter-icon">{filter.icon}</span>
                    <span>{filter.label}</span>
                    <b>{count}</b>
                    {checked ? <Check weight="bold" /> : null}
                  </label>
                )
              })}
            </div>
          </section>

          <section className="summary-section interpretation-rule">
            <h2>Interpretation rule</h2>
            <p>
              A candidate remains a pending lead. Evidence similarity never
              becomes ownership probability. Human review is required before an
              assertion can be emphasized.
            </p>
          </section>
        </div>
      </ScrollArea>
    </aside>
  )
}
