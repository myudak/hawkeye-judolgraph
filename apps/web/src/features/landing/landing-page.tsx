import {
  ArrowRight,
  Binoculars,
  CardsThree,
  CaretDown,
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
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
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

const hawkeyeBanner = "/assets/hawkeye-banner.png"
const hawkeyeBannerLight = "/assets/hawkeye-banner-light.jpg"

const exampleSites = [
  "https://888.com",
  "https://888casino.com",
  "https://888poker.com",
  "https://888sport.com",
  "https://betfair.com",
  "https://paddypower.com",
  "https://skybet.com",
  "https://skyvegas.com",
  "https://bet365.com",
  "https://williamhill.com",
  "https://qq101xfw.com/",
  "https://qq888bet4cv.com/",
] as const

const controlSite = "https://myudak.com"

type CaseFilter = "all" | "active" | "complete" | "review" | "error"
type CaseLayout = "grid" | "list"
type Language = "en" | "id"

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

const filterOptions: Array<{
  key: CaseFilter
  label: Record<Language, string>
}> = [
  { key: "all", label: { en: "All", id: "Semua" } },
  { key: "active", label: { en: "Active", id: "Aktif" } },
  { key: "complete", label: { en: "Complete", id: "Selesai" } },
  {
    key: "review",
    label: { en: "Needs review", id: "Perlu ditinjau" },
  },
  {
    key: "error",
    label: { en: "Integrity errors", id: "Error integritas" },
  },
]

const landingCopy = {
  en: {
    launchTitle: "Capture a public evidence trail",
    launchDescription:
      "Preserve first. Extract deterministically. Review every relationship.",
    seedLabel: "Public seed URL",
    seedPlaceholder: "Enter a public web address",
    exampleSites: "Example sites",
    chooseExample: "Choose an example site",
    knownSites: "Public examples",
    controlSite: "Non-gambling control",
    nameLabel: "Investigation name",
    optional: "optional",
    namePlaceholder: "e.g. Public contact and related-site review",
    scopeTitle: "Public, read-only scope.",
    scopeBody:
      "No sign-in, forms, messaging, purchases, downloads, or access-control bypass.",
    checkingAgent: "Checking agent",
    safeFallback: "Safe fallback",
    creatingWorkspace: "Creating workspace",
    startInvestigation: "Start investigation",
    cases: "Cases",
    casesDescription:
      "Your saved investigations and verified evidence collections.",
    search: "Search cases…",
    sort: "Sort cases",
    newest: "Newest first",
    oldest: "Oldest first",
    domain: "Domain name",
    filter: "Filter cases",
    layout: "Case layout",
    grid: "Grid view",
    list: "List view",
    pages: "Pages",
    indicators: "Indicators",
    candidates: "Candidates",
    updated: "Updated WIB",
    noCases: "No cases match this view",
    noCasesHelp:
      "Adjust the search/filter or start a new bounded investigation.",
    boundaries: "Evidence boundaries",
    immutableTitle: "Immutable evidence",
    immutableBody: "Artifacts are hash-verified before display.",
    extractionTitle: "Transparent extraction",
    extractionBody: "Every observation retains provenance.",
    neutralTitle: "Relationship neutral",
    neutralBody: "Candidates remain pending until review.",
  },
  id: {
    launchTitle: "Tangkap jejak bukti publik",
    launchDescription:
      "Simpan lebih dulu. Ekstrak secara deterministik. Tinjau setiap relasi.",
    seedLabel: "URL publik awal",
    seedPlaceholder: "Masukkan alamat web publik",
    exampleSites: "Contoh situs",
    chooseExample: "Pilih contoh situs",
    knownSites: "Contoh publik",
    controlSite: "Kontrol non-judol",
    nameLabel: "Nama investigasi",
    optional: "opsional",
    namePlaceholder: "contoh: Penelusuran kontak dan situs terkait",
    scopeTitle: "Ruang lingkup publik dan hanya-baca.",
    scopeBody:
      "Tanpa login, pengiriman formulir, pesan, pembelian, unduhan, atau bypass kontrol akses.",
    checkingAgent: "Memeriksa agen",
    safeFallback: "Fallback aman",
    creatingWorkspace: "Membuat workspace",
    startInvestigation: "Mulai investigasi",
    cases: "Kasus",
    casesDescription: "Investigasi tersimpan dan koleksi bukti terverifikasi.",
    search: "Cari kasus…",
    sort: "Urutkan kasus",
    newest: "Terbaru",
    oldest: "Terlama",
    domain: "Nama domain",
    filter: "Filter kasus",
    layout: "Tampilan kasus",
    grid: "Tampilan grid",
    list: "Tampilan daftar",
    pages: "Halaman",
    indicators: "Indikator",
    candidates: "Kandidat",
    updated: "Diperbarui WIB",
    noCases: "Tidak ada kasus pada tampilan ini",
    noCasesHelp: "Ubah pencarian/filter atau mulai investigasi baru.",
    boundaries: "Batas pengumpulan bukti",
    immutableTitle: "Bukti tidak dapat diubah",
    immutableBody: "Hash artefak diverifikasi sebelum ditampilkan.",
    extractionTitle: "Ekstraksi transparan",
    extractionBody: "Setiap observasi menyimpan asal-usulnya.",
    neutralTitle: "Relasi tetap netral",
    neutralBody: "Kandidat tetap tertunda sampai ditinjau.",
  },
} as const

function localizedStateLabel(entry: CaseEntry, language: Language) {
  if (language === "en") return entry.stateLabel
  if (entry.state === "error") return "Error integritas"
  if (entry.state === "review") return "Perlu ditinjau"
  if (entry.state === "active")
    return entry.stateLabel === "Queued" ? "Dalam antrean" : "Berjalan"
  if (entry.stateLabel === "Recollected") return "Dikoleksi ulang"
  if (entry.stateLabel === "Captured · limited") return "Tangkapan terbatas"
  return "Selesai"
}

function StateBadge({
  entry,
  language,
}: {
  entry: CaseEntry
  language: Language
}) {
  const tone =
    entry.state === "review"
      ? "warning"
      : entry.state === "error"
        ? "danger"
        : entry.state === "active"
          ? "cyan"
          : "success"
  return (
    <Badge className={`status-badge status-${tone}`}>
      {localizedStateLabel(entry, language)}
    </Badge>
  )
}

function CaseCard({
  entry,
  layout,
  language,
}: {
  entry: CaseEntry
  layout: CaseLayout
  language: Language
}) {
  const navigate = useNavigate()
  const disabled = entry.integrity === "error"
  const copy = landingCopy[language]
  const stateLabel = localizedStateLabel(entry, language)
  return (
    <button
      type="button"
      data-state={entry.state}
      className={cn(
        "case-card group",
        layout === "list" && "case-card-list",
        disabled && "case-card-error"
      )}
      disabled={disabled}
      onClick={() => navigate(`/workspace/${entry.kind}/${entry.id}`)}
      aria-label={`${entry.title}, ${stateLabel}, ${entry.pages} ${copy.pages}, ${entry.indicators} ${copy.indicators}`}
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
        <StateBadge entry={entry} language={language} />
      </span>
      <span className="case-card-rule" />
      <span className="case-metrics">
        <span>
          <CardsThree weight="duotone" />
          <b>{entry.pages}</b>
          <small>{copy.pages}</small>
        </span>
        <span>
          <Binoculars weight="duotone" />
          <b>{entry.indicators}</b>
          <small>{copy.indicators}</small>
        </span>
        <span>
          <Funnel weight="duotone" />
          <b>{entry.candidates}</b>
          <small>{copy.candidates}</small>
        </span>
        <span>
          <ClockCounterClockwise weight="duotone" />
          <b>{formatTime(entry.updated)}</b>
          <small>{entry.error || copy.updated}</small>
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
  const [language, setLanguage] = useState<Language>(() =>
    window.localStorage.getItem("hawk-eye-language") === "id" ? "id" : "en"
  )
  const deferredQuery = useDeferredValue(query)
  const copy = landingCopy[language]

  useEffect(() => {
    document.documentElement.lang = language
  }, [language])

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

  const toggleLanguage = () => {
    setLanguage((current) => {
      const next = current === "en" ? "id" : "en"
      window.localStorage.setItem("hawk-eye-language", next)
      return next
    })
  }

  const capabilityReady = [
    "model_ready",
    "model_configured_unverified",
  ].includes(capability.data?.state || "")

  return (
    <div className="app-page landing-page">
      <AppHeader
        context="landing"
        language={language}
        onLanguageToggle={toggleLanguage}
      />
      <main className="landing-main">
        <figure className="brand-hero-banner">
          <img
            className="theme-asset-dark"
            src={hawkeyeBanner}
            alt="HAWK-EYE investigation banner"
          />
          <img
            className="theme-asset-light"
            src={hawkeyeBannerLight}
            alt="HAWK-EYE investigation banner in light mode"
          />
        </figure>
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
              <h1 id="launch-title">{copy.launchTitle}</h1>
              <p>{copy.launchDescription}</p>
            </div>
          </div>

          <form className="launch-form" onSubmit={submit}>
            <div className="field-stack launch-url-field">
              <Label htmlFor="seed-url">{copy.seedLabel}</Label>
              <span className="input-shell">
                <LinkSimple weight="bold" />
                <Input
                  id="seed-url"
                  type="url"
                  required
                  value={seedUrl}
                  onChange={(event) => setSeedUrl(event.target.value)}
                  placeholder={copy.seedPlaceholder}
                  autoComplete="url"
                />
                <DropdownMenu>
                  <DropdownMenuTrigger
                    render={
                      <button
                        className="seed-example-trigger"
                        type="button"
                        aria-label={copy.chooseExample}
                        title={copy.chooseExample}
                      >
                        <span>{copy.exampleSites}</span>
                        <CaretDown weight="bold" />
                      </button>
                    }
                  />
                  <DropdownMenuContent
                    align="end"
                    className="seed-example-menu w-72"
                  >
                    <DropdownMenuGroup>
                      <DropdownMenuLabel>{copy.knownSites}</DropdownMenuLabel>
                      {exampleSites.map((site) => (
                        <DropdownMenuItem
                          key={site}
                          onClick={() => setSeedUrl(site)}
                        >
                          <GlobeHemisphereWest />
                          <span>{hostnameFrom(site)}</span>
                          {seedUrl === site ? (
                            <CheckCircle className="ml-auto" weight="fill" />
                          ) : null}
                        </DropdownMenuItem>
                      ))}
                    </DropdownMenuGroup>
                    <DropdownMenuGroup>
                      <DropdownMenuLabel>{copy.controlSite}</DropdownMenuLabel>
                      <DropdownMenuItem onClick={() => setSeedUrl(controlSite)}>
                        <ShieldCheck />
                        <span>{hostnameFrom(controlSite)}</span>
                        {seedUrl === controlSite ? (
                          <CheckCircle className="ml-auto" weight="fill" />
                        ) : null}
                      </DropdownMenuItem>
                    </DropdownMenuGroup>
                  </DropdownMenuContent>
                </DropdownMenu>
              </span>
            </div>
            <div className="field-stack">
              <Label htmlFor="investigation-name">
                {copy.nameLabel} <span>({copy.optional})</span>
              </Label>
              <Input
                id="investigation-name"
                value={investigationName}
                onChange={(event) => setInvestigationName(event.target.value)}
                placeholder={copy.namePlaceholder}
                maxLength={200}
              />
            </div>
            <div className="launch-footer">
              <div className="scope-notice">
                <LockKey weight="duotone" />
                <span>
                  <b>{copy.scopeTitle}</b> {copy.scopeBody}
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
                  ? copy.checkingAgent
                  : capabilityReady
                    ? capability.data?.selected_model || "Model configured"
                    : copy.safeFallback}
              </div>
              <Button
                type="submit"
                size="lg"
                className="launch-button"
                disabled={startJob.isPending}
              >
                {startJob.isPending
                  ? copy.creatingWorkspace
                  : copy.startInvestigation}
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
                <h2 id="cases-title">{copy.cases}</h2>
                <p>{copy.casesDescription}</p>
              </div>
            </div>
            <div className="case-controls">
              <span className="search-shell">
                <MagnifyingGlass />
                <Input
                  type="search"
                  placeholder={copy.search}
                  value={query}
                  onChange={(event) => setQuery(event.target.value)}
                  aria-label={copy.search}
                />
              </span>
              <Select
                value={sort}
                onValueChange={(value) => setSort(value ?? "newest")}
              >
                <SelectTrigger className="sort-select" aria-label={copy.sort}>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="newest">{copy.newest}</SelectItem>
                  <SelectItem value="oldest">{copy.oldest}</SelectItem>
                  <SelectItem value="name">{copy.domain}</SelectItem>
                </SelectContent>
              </Select>
              <div className="case-filters" aria-label={copy.filter}>
                {filterOptions.map((item) => (
                  <Button
                    key={item.key}
                    type="button"
                    size="sm"
                    variant={filter === item.key ? "default" : "ghost"}
                    aria-pressed={filter === item.key}
                    onClick={() => setFilter(item.key)}
                  >
                    {item.label[language]}
                  </Button>
                ))}
              </div>
              <div className="layout-toggle" aria-label={copy.layout}>
                <Button
                  size="icon-sm"
                  variant={layout === "grid" ? "secondary" : "ghost"}
                  aria-label={copy.grid}
                  aria-pressed={layout === "grid"}
                  onClick={() => setLayout("grid")}
                >
                  <GridFour />
                </Button>
                <Button
                  size="icon-sm"
                  variant={layout === "list" ? "secondary" : "ghost"}
                  aria-label={copy.list}
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
                  language={language}
                />
              ))}
            </div>
          ) : (
            <div className="empty-cases">
              <Sparkle weight="duotone" />
              <strong>{copy.noCases}</strong>
              <p>{copy.noCasesHelp}</p>
            </div>
          )}
        </section>

        <aside className="landing-principles" aria-label={copy.boundaries}>
          <span>
            <ShieldCheck weight="duotone" />
            <b>{copy.immutableTitle}</b> {copy.immutableBody}
          </span>
          <span>
            <Binoculars weight="duotone" />
            <b>{copy.extractionTitle}</b> {copy.extractionBody}
          </span>
          <span>
            <WarningCircle weight="duotone" />
            <b>{copy.neutralTitle}</b> {copy.neutralBody}
          </span>
        </aside>
      </main>
    </div>
  )
}
