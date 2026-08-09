import {
  ArrowRight,
  Binoculars,
  CardsThree,
  CheckCircle,
  ClockCounterClockwise,
  Database,
  Funnel,
  GlobeHemisphereWest,
  GridFour,
  LinkSimple,
  List,
  LockKey,
  MagnifyingGlass,
  Pulse,
  ShieldCheck,
  Sparkle,
  WarningCircle,
} from "@phosphor-icons/react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useDeferredValue, useEffect, useMemo, useState } from "react"
import { useNavigate } from "react-router-dom"
import { toast } from "sonner"

import { api } from "@/api/client"
import type { CaseListItem, RunListItem } from "@/api/types"
import { AppHeader } from "@/components/app-header"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Skeleton } from "@/components/ui/skeleton"
import { useCapability, useIndexes } from "@/hooks/use-indexes"
import { formatTime, hostnameFrom, titleCase } from "@/lib/format"
import { cn } from "@/lib/utils"

type CaseFilter = "all" | "active" | "complete" | "review" | "error"
type CaseLayout = "grid" | "list"

interface CaseEntry {
  kind: "run" | "case"
  id: string
  caseId: string
  title: string
  updated?: string | null
  pages: number
  indicators: number
  candidates: number
  state: CaseFilter
  stateLabel: string
  integrity: string
  error?: string
}

function stateFor(
  value?: string | null,
  integrity?: string
): Pick<CaseEntry, "state" | "stateLabel"> {
  if (integrity === "error")
    return { state: "error", stateLabel: "Integrity error" }
  const state = String(value || "complete")
  if (
    ["waiting_for_approval", "needs_review", "review_required"].includes(state)
  ) {
    return { state: "review", stateLabel: "Needs review" }
  }
  if (["queued", "running"].includes(state))
    return { state: "active", stateLabel: titleCase(state) }
  if (state === "recollected")
    return { state: "complete", stateLabel: "Recollected" }
  if (state === "limited")
    return { state: "complete", stateLabel: "Captured · limited" }
  return { state: "complete", stateLabel: "Complete" }
}

function mergeEntries(cases: CaseListItem[], runs: RunListItem[]): CaseEntry[] {
  const casesById = new Map(cases.map((item) => [item.case_id, item]))
  const represented = new Set(
    runs.map((item) => item.source_case_id).filter(Boolean)
  )
  const runEntries = runs.map((run): CaseEntry => {
    const source = run.source_case_id
      ? casesById.get(run.source_case_id)
      : undefined
    const state = stateFor(
      run.lead_status || run.agent_stop_reason,
      source?.integrity
    )
    return {
      kind: "run",
      id: run.workspace_id,
      caseId: run.case_id,
      title: hostnameFrom(
        run.seed_url || source?.final_url_display || run.case_id
      ),
      updated: run.updated_at,
      pages: source?.page_count ?? 0,
      indicators: source?.gambling_indicator_count ?? 0,
      candidates: source?.candidate_count ?? 0,
      integrity: source?.integrity ?? "verified",
      ...state,
    }
  })
  const caseEntries = cases
    .filter((item) => !represented.has(item.case_id))
    .map((item): CaseEntry => {
      const state = stateFor(item.capture_adequacy, item.integrity)
      return {
        kind: "case",
        id: item.case_id,
        caseId: item.case_id,
        title:
          item.integrity === "verified"
            ? hostnameFrom(item.final_url_display || item.seed_url_display)
            : "Unverified case package",
        updated: item.completed_at || item.started_at,
        pages: item.page_count ?? 0,
        indicators: item.gambling_indicator_count ?? 0,
        candidates: item.candidate_count ?? 0,
        integrity: item.integrity,
        error: item.error,
        ...state,
      }
    })
  return [...runEntries, ...caseEntries]
}

const filterOptions: Array<{ key: CaseFilter; label: string }> = [
  { key: "all", label: "All" },
  { key: "active", label: "Active" },
  { key: "complete", label: "Complete" },
  { key: "review", label: "Needs review" },
  { key: "error", label: "Integrity errors" },
]

function StateBadge({ entry }: { entry: CaseEntry }) {
  const tone =
    entry.state === "review"
      ? "warning"
      : entry.state === "error"
        ? "danger"
        : entry.state === "active"
          ? "cyan"
          : "success"
  return (
    <Badge className={`status-badge status-${tone}`}>{entry.stateLabel}</Badge>
  )
}

function CaseCard({ entry, layout }: { entry: CaseEntry; layout: CaseLayout }) {
  const navigate = useNavigate()
  const disabled = entry.integrity === "error"
  return (
    <button
      type="button"
      className={cn(
        "case-card group",
        layout === "list" && "case-card-list",
        disabled && "case-card-error"
      )}
      disabled={disabled}
      onClick={() => navigate(`/workspace/${entry.kind}/${entry.id}`)}
      aria-label={`${entry.title}, ${entry.stateLabel}, ${entry.pages} pages, ${entry.indicators} indicators`}
    >
      <span className="case-card-accent" />
      <span className="case-card-head">
        <span className="case-identity">
          <span className="case-domain-icon">
            <GlobeHemisphereWest weight="duotone" />
          </span>
          <span>
            <strong>{entry.title}</strong>
            <small>{entry.caseId}</small>
          </span>
        </span>
        <StateBadge entry={entry} />
      </span>
      <span className="case-card-rule" />
      <span className="case-metrics">
        <span>
          <CardsThree weight="duotone" />
          <b>{entry.pages}</b>
          <small>Pages</small>
        </span>
        <span>
          <Binoculars weight="duotone" />
          <b>{entry.indicators}</b>
          <small>Indicators</small>
        </span>
        <span>
          <Funnel weight="duotone" />
          <b>{entry.candidates}</b>
          <small>Candidates</small>
        </span>
        <span>
          <ClockCounterClockwise weight="duotone" />
          <b>{formatTime(entry.updated)}</b>
          <small>{entry.error || "Updated WIB"}</small>
        </span>
      </span>
      <span className="case-open">
        <ArrowRight weight="bold" />
      </span>
    </button>
  )
}

export function LandingPage() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { cases, runs, isPending } = useIndexes()
  const capability = useCapability()
  const activeJob = useQuery({
    queryKey: ["active-job"],
    queryFn: api.activeJob,
    staleTime: 0,
    retry: false,
  })
  const [seedUrl, setSeedUrl] = useState("https://qq101xfw.com")
  const [investigationName, setInvestigationName] = useState("")
  const [query, setQuery] = useState("")
  const [filter, setFilter] = useState<CaseFilter>("all")
  const [layout, setLayout] = useState<CaseLayout>("grid")
  const [sort, setSort] = useState("newest")
  const deferredQuery = useDeferredValue(query)

  useEffect(() => {
    const job = activeJob.data?.job
    if (job && ["queued", "running"].includes(job.status))
      navigate(`/scan/${job.job_id}`, { replace: true })
  }, [activeJob.data?.job, navigate])

  const startJob = useMutation({
    mutationFn: api.startJob,
    onSuccess: (job) => {
      queryClient.setQueryData(["job", job.job_id], job)
      navigate(`/scan/${job.job_id}`)
    },
    onError: (error) => toast.error(error.message),
  })

  const entries = useMemo(() => {
    const lowered = deferredQuery.trim().toLowerCase()
    const filtered = mergeEntries(cases, runs).filter((entry) => {
      const filterMatches = filter === "all" || entry.state === filter
      const queryMatches =
        !lowered ||
        `${entry.title} ${entry.caseId} ${entry.stateLabel}`
          .toLowerCase()
          .includes(lowered)
      return filterMatches && queryMatches
    })
    return filtered.toSorted((left, right) => {
      if (sort === "name") return left.title.localeCompare(right.title)
      const delta =
        new Date(left.updated || 0).getTime() -
        new Date(right.updated || 0).getTime()
      return sort === "oldest" ? delta : -delta
    })
  }, [cases, runs, deferredQuery, filter, sort])

  const submit = (event: React.FormEvent) => {
    event.preventDefault()
    startJob.mutate({
      seed_url: seedUrl.trim(),
      investigation_name: investigationName.trim(),
      investigation_mode: "guided",
    })
  }

  const capabilityReady = capability.data?.state === "codex_ready"

  return (
    <div className="app-page landing-page">
      <AppHeader context="landing" />
      <main className="landing-main">
        <section className="launch-section" aria-labelledby="launch-title">
          <div className="launch-orbit" aria-hidden="true">
            <span />
            <span />
            <span />
          </div>
          <div className="launch-heading">
            <span className="section-icon">
              <Pulse weight="duotone" />
            </span>
            <div>
              <p className="eyebrow">START NEW INVESTIGATION</p>
              <h1 id="launch-title">Capture a public evidence trail</h1>
              <p>
                Preserve first. Extract deterministically. Review every
                relationship.
              </p>
            </div>
          </div>

          <form className="launch-form" onSubmit={submit}>
            <div className="field-stack launch-url-field">
              <Label htmlFor="seed-url">Public seed URL</Label>
              <span className="input-shell">
                <LinkSimple weight="bold" />
                <Input
                  id="seed-url"
                  type="url"
                  required
                  value={seedUrl}
                  onChange={(event) => setSeedUrl(event.target.value)}
                  placeholder="Enter a public web address"
                  autoComplete="url"
                />
                <CheckCircle className="input-valid" weight="fill" />
              </span>
            </div>
            <div className="field-stack">
              <Label htmlFor="investigation-name">
                Investigation name <span>(optional)</span>
              </Label>
              <Input
                id="investigation-name"
                value={investigationName}
                onChange={(event) => setInvestigationName(event.target.value)}
                placeholder="e.g. Public contact and related-site review"
                maxLength={200}
              />
            </div>
            <div className="launch-footer">
              <div className="scope-notice">
                <LockKey weight="duotone" />
                <span>
                  <b>Public, read-only scope.</b> No sign-in, forms, messaging,
                  purchases, downloads, or access-control bypass.
                </span>
              </div>
              <div
                className={cn(
                  "capability-pill",
                  capabilityReady && "capability-ready"
                )}
              >
                <span />
                {capability.isPending
                  ? "Checking agent"
                  : capabilityReady
                    ? capability.data?.selected_model || "Codex ready"
                    : "Safe fallback"}
              </div>
              <Button
                type="submit"
                size="lg"
                className="launch-button"
                disabled={startJob.isPending}
              >
                {startJob.isPending
                  ? "Creating workspace"
                  : "Start investigation"}
                <ArrowRight weight="bold" />
              </Button>
            </div>
          </form>
        </section>

        <section className="cases-section" aria-labelledby="cases-title">
          <header className="cases-header">
            <div className="cases-title">
              <span className="section-icon">
                <Database weight="duotone" />
              </span>
              <div>
                <h2 id="cases-title">Cases</h2>
                <p>
                  Your saved investigations and verified evidence collections.
                </p>
              </div>
            </div>
            <div className="case-controls">
              <span className="search-shell">
                <MagnifyingGlass />
                <Input
                  type="search"
                  placeholder="Search cases…"
                  value={query}
                  onChange={(event) => setQuery(event.target.value)}
                  aria-label="Search cases"
                />
              </span>
              <Select
                value={sort}
                onValueChange={(value) => setSort(value ?? "newest")}
              >
                <SelectTrigger className="sort-select" aria-label="Sort cases">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="newest">Newest first</SelectItem>
                  <SelectItem value="oldest">Oldest first</SelectItem>
                  <SelectItem value="name">Domain name</SelectItem>
                </SelectContent>
              </Select>
              <div className="case-filters" aria-label="Filter cases">
                {filterOptions.map((item) => (
                  <Button
                    key={item.key}
                    type="button"
                    size="sm"
                    variant={filter === item.key ? "default" : "ghost"}
                    aria-pressed={filter === item.key}
                    onClick={() => setFilter(item.key)}
                  >
                    {item.label}
                  </Button>
                ))}
              </div>
              <div className="layout-toggle" aria-label="Case layout">
                <Button
                  size="icon-sm"
                  variant={layout === "grid" ? "secondary" : "ghost"}
                  aria-label="Grid view"
                  aria-pressed={layout === "grid"}
                  onClick={() => setLayout("grid")}
                >
                  <GridFour />
                </Button>
                <Button
                  size="icon-sm"
                  variant={layout === "list" ? "secondary" : "ghost"}
                  aria-label="List view"
                  aria-pressed={layout === "list"}
                  onClick={() => setLayout("list")}
                >
                  <List />
                </Button>
              </div>
            </div>
          </header>

          {isPending ? (
            <div className="case-grid">
              {Array.from({ length: 6 }).map((_, index) => (
                <Card key={index} className="case-skeleton">
                  <CardContent>
                    <Skeleton className="h-5 w-40" />
                    <Skeleton className="mt-4 h-20 w-full" />
                  </CardContent>
                </Card>
              ))}
            </div>
          ) : entries.length ? (
            <div
              className={cn("case-grid", layout === "list" && "case-grid-list")}
            >
              {entries.map((entry) => (
                <CaseCard
                  key={`${entry.kind}:${entry.id}`}
                  entry={entry}
                  layout={layout}
                />
              ))}
            </div>
          ) : (
            <div className="empty-cases">
              <Sparkle weight="duotone" />
              <strong>No cases match this view</strong>
              <p>
                Adjust the search/filter or start a new bounded investigation.
              </p>
            </div>
          )}
        </section>

        <aside className="landing-principles" aria-label="Evidence boundaries">
          <span>
            <ShieldCheck weight="duotone" />
            <b>Immutable evidence</b> Artifacts are hash-verified before
            display.
          </span>
          <span>
            <Binoculars weight="duotone" />
            <b>Transparent extraction</b> Every observation retains provenance.
          </span>
          <span>
            <WarningCircle weight="duotone" />
            <b>Relationship neutral</b> Candidates remain pending until review.
          </span>
        </aside>
      </main>
    </div>
  )
}
