import {
  ArrowRight,
  FileText,
  Globe,
  MagnifyingGlass,
  Pulse,
  SidebarSimple,
  Warning,
} from "@phosphor-icons/react"
import { useQuery } from "@tanstack/react-query"
import { useMemo, useState } from "react"
import { useNavigate, useParams } from "react-router-dom"

import { api } from "@/api/client"
import type { EvidenceSource, InvestigationEvent } from "@/api/types"
import { AppHeader } from "@/components/app-header"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Skeleton } from "@/components/ui/skeleton"
import { useIndexes } from "@/hooks/use-indexes"
import { hostnameFrom } from "@/lib/format"
import {
  buildCaseProjection,
  buildRunProjection,
  type GraphLens,
  type GraphNode,
  type VisualKind,
} from "@/lib/graph"
import { cn } from "@/lib/utils"
import { CaseSummary } from "@/features/workspace/case-summary"
import { EvidenceGraph } from "@/features/workspace/evidence-graph"
import { EvidenceInspector } from "@/features/workspace/evidence-inspector"
import { InvestigationTimeline } from "@/features/workspace/timeline"

const ALL_FILTERS = new Set<VisualKind>([
  "page",
  "contact",
  "brand",
  "transaction",
  "offer",
  "destination",
  "candidate",
  "other",
])

export function WorkspacePage() {
  const { kind, id } = useParams<{ kind: "case" | "run"; id: string }>()
  const navigate = useNavigate()
  const { cases } = useIndexes()
  const [filters, setFilters] = useState<Set<VisualKind>>(
    () => new Set(ALL_FILTERS)
  )
  const [selection, setSelection] = useState<{
    sourceKey: string
    nodeId: string | null
    event: InvestigationEvent | null
  }>({ sourceKey: "", nodeId: null, event: null })
  const [searchQuery, setSearchQuery] = useState("")
  const [graphLens, setGraphLens] = useState<GraphLens>("evidence")
  const [language, setLanguage] = useState<"en" | "id">(
    () =>
      (window.localStorage.getItem("hawk-eye-language") as "en" | "id") || "en"
  )
  const [leftCollapsed, setLeftCollapsed] = useState(false)
  const [rightCollapsed, setRightCollapsed] = useState(false)
  const [timelineSelection, setTimelineSelection] = useState({
    sourceKey: "",
    index: 0,
  })

  const detailsQuery = useQuery({
    queryKey: [kind, id],
    queryFn: async (): Promise<EvidenceSource> => {
      if (!id || (kind !== "case" && kind !== "run"))
        throw new Error("Invalid evidence route")
      if (kind === "case") return { kind, id, details: await api.getCase(id) }
      return { kind, id, details: await api.getRun(id) }
    },
    enabled: Boolean(id && (kind === "case" || kind === "run")),
  })

  const source = detailsQuery.data
  const projection = useMemo(() => {
    if (!source) return null
    return source.kind === "case"
      ? buildCaseProjection(source.details, cases)
      : buildRunProjection(source.details)
  }, [cases, source])

  const sourceKey = `${kind}:${id}`
  const defaultNode =
    projection?.nodes.find((node) => node.primary) ?? projection?.nodes[0]
  const selectedId =
    selection.sourceKey === sourceKey &&
    projection?.nodes.some((node) => node.id === selection.nodeId)
      ? selection.nodeId
      : (defaultNode?.id ?? null)
  const selectedEvent =
    selection.sourceKey === sourceKey ? selection.event : null
  const selectedNode =
    projection?.nodes.find((node) => node.id === selectedId) ?? null
  const timelineIndex =
    timelineSelection.sourceKey === sourceKey
      ? Math.min(
          timelineSelection.index,
          Math.max(0, (projection?.timeline.length ?? 1) - 1)
        )
      : Math.max(0, (projection?.timeline.length ?? 1) - 1)
  const cutoff =
    projection?.timeline[timelineIndex]?.sequence ?? Number.POSITIVE_INFINITY

  const selectNode = (node: GraphNode) => {
    setSelection({ sourceKey, nodeId: node.id, event: null })
  }

  const selectTimeline = (index: number) => {
    if (!projection) return
    const item = projection.timeline[index]
    if (!item) return
    setTimelineSelection({ sourceKey, index })
    const target = item.targetId
      ? projection.nodes.find((node) => node.id === item.targetId)
      : undefined
    if (target) {
      setSelection({ sourceKey, nodeId: target.id, event: null })
    } else if (item.event) {
      setSelection({ sourceKey, nodeId: selectedId, event: item.event })
    }
  }

  const toggleFilter = (filter: VisualKind, enabled: boolean) => {
    setFilters((current) => {
      const next = new Set(current)
      if (enabled) next.add(filter)
      else next.delete(filter)
      return next
    })
  }

  const toggleLanguage = () => {
    setLanguage((current) => {
      const next = current === "en" ? "id" : "en"
      window.localStorage.setItem("hawk-eye-language", next)
      return next
    })
  }

  if (detailsQuery.isError) {
    return (
      <div className="app-page workspace-page">
        <AppHeader context="workspace" language={language} />
        <main className="workspace-error">
          <Warning weight="duotone" />
          <h1>Evidence workspace unavailable</h1>
          <p>{detailsQuery.error.message}</p>
          <Button onClick={() => navigate("/")}>Return to cases</Button>
        </main>
      </div>
    )
  }

  if (detailsQuery.isPending || !source || !projection) {
    return (
      <div className="app-page workspace-page">
        <AppHeader
          context="workspace"
          currentValue={kind && id ? `${kind}:${id}` : undefined}
          language={language}
        />
        <main className="workspace-loading">
          <Skeleton className="h-14 w-full" />
          <div>
            <Skeleton />
            <Skeleton />
            <Skeleton />
          </div>
        </main>
      </div>
    )
  }

  const run = source.kind === "run" ? source.details : undefined
  const standaloneCase = source.kind === "case" ? source.details : undefined
  const caseDetails = run?.source_case ?? standaloneCase
  const host = hostnameFrom(
    run
      ? run.seed_url || caseDetails?.final_url_display || run.case_id
      : standaloneCase?.final_url_display || standaloneCase?.seed_url_display
  )
  const url = run
    ? run.seed_url || caseDetails?.final_url_display || run.case_id
    : standaloneCase?.final_url_display ||
      standaloneCase?.seed_url_display ||
      standaloneCase?.case_id

  return (
    <div className="app-page workspace-page">
      <AppHeader
        context="workspace"
        currentValue={`${source.kind}:${source.id}`}
        language={language}
      />
      <main className="workspace-main">
        <header className="workspace-command-bar">
          <div className="workspace-identity">
            <span className="eyebrow">
              <Pulse weight="fill" />
              {language === "id"
                ? " INVESTIGASI AKTIF"
                : " ACTIVE INVESTIGATION"}
            </span>
            <strong>{host}</strong>
          </div>
          <div className="workspace-url">
            <Globe weight="duotone" />
            <span>{url}</span>
          </div>
          <span className="workspace-search">
            <MagnifyingGlass />
            <Input
              type="search"
              value={searchQuery}
              onChange={(event) => setSearchQuery(event.target.value)}
              placeholder={
                language === "id" ? "Cari node graph…" : "Search graph nodes…"
              }
              aria-label="Search evidence graph"
            />
          </span>
          <div className="workspace-display-controls">
            <Button
              size="sm"
              variant="outline"
              aria-label={
                language === "id"
                  ? "Switch to English"
                  : "Ganti ke Bahasa Indonesia"
              }
              title={
                language === "id" ? "Switch to English" : "Bahasa Indonesia"
              }
              onClick={toggleLanguage}
            >
              {language === "id" ? "ID" : "EN"}
            </Button>
            <Button
              size="icon-sm"
              variant="outline"
              aria-pressed={!leftCollapsed}
              aria-label={
                leftCollapsed
                  ? language === "id"
                    ? "Tampilkan ringkasan kasus"
                    : "Show case summary"
                  : language === "id"
                    ? "Sembunyikan ringkasan kasus"
                    : "Hide case summary"
              }
              title={language === "id" ? "Panel kasus" : "Case panel"}
              onClick={() => setLeftCollapsed((value) => !value)}
            >
              <SidebarSimple weight={leftCollapsed ? "regular" : "fill"} />
            </Button>
            <Button
              size="icon-sm"
              variant="outline"
              aria-pressed={!rightCollapsed}
              aria-label={
                rightCollapsed
                  ? language === "id"
                    ? "Tampilkan panel bukti"
                    : "Show evidence panel"
                  : language === "id"
                    ? "Sembunyikan panel bukti"
                    : "Hide evidence panel"
              }
              title={language === "id" ? "Panel bukti" : "Evidence panel"}
              onClick={() => setRightCollapsed((value) => !value)}
            >
              <SidebarSimple
                className="right-panel-icon"
                weight={rightCollapsed ? "regular" : "fill"}
              />
            </Button>
          </div>
          <Button
            className="summary-button"
            onClick={() => navigate(`/summary/${source.kind}/${source.id}`)}
          >
            <FileText weight="duotone" />
            {language === "id" ? "Lihat ringkasan" : "View summary"}
            <ArrowRight />
          </Button>
        </header>

        <section
          className={cn(
            "workspace-grid",
            leftCollapsed && "workspace-left-collapsed",
            rightCollapsed && "workspace-right-collapsed"
          )}
        >
          <CaseSummary
            source={source}
            projection={projection}
            filters={filters}
            onToggleFilter={toggleFilter}
            language={language}
          />
          <div className="graph-workspace">
            <EvidenceGraph
              projection={projection}
              selectedId={selectedId}
              onSelect={selectNode}
              filters={filters}
              playbackCutoff={cutoff}
              searchQuery={searchQuery}
              lens={graphLens}
              onLensChange={setGraphLens}
              language={language}
            />
            <InvestigationTimeline
              timeline={projection.timeline}
              activeIndex={timelineIndex}
              onSelect={selectTimeline}
              language={language}
            />
          </div>
          <EvidenceInspector
            source={source}
            projection={projection}
            selectedNode={selectedNode}
            selectedEvent={selectedEvent}
            onFocusNode={(nodeId) =>
              setSelection({ sourceKey, nodeId, event: null })
            }
            language={language}
          />
        </section>
      </main>
    </div>
  )
}
