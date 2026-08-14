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
import { useEffect, useMemo, useRef, useState } from "react"
import { useNavigate, useParams } from "react-router-dom"
import { toast } from "sonner"

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

type Language = "en" | "id"

const stageGroups = [
  {
    label: { en: "Validate target", id: "Periksa alamat situs" },
    stages: ["queued", "validating_seed", "launching_browser"],
    icon: ShieldCheck,
  },
  {
    label: { en: "Capture pages", id: "Ambil halaman" },
    stages: ["initializing_case", "capturing_page"],
    icon: Browser,
  },
  {
    label: { en: "Preserve & extract", id: "Simpan & baca temuan" },
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
    label: { en: "Bounded investigation", id: "Telusuri secara aman" },
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
    label: { en: "Classify & graph", id: "Susun graph" },
    stages: ["classifying_indicators", "building_graph"],
    icon: Graph,
  },
  {
    label: { en: "Finalize case", id: "Selesaikan kasus" },
    stages: ["completed"],
    icon: FlagCheckered,
  },
]

const stageCopy: Record<string, Record<Language, [string, string]>> = {
  queued: {
    en: [
      "Preparing investigation",
      "Reserving a safe workspace for this site.",
    ],
    id: [
      "Menyiapkan investigasi",
      "Menyiapkan ruang kerja yang aman untuk situs ini.",
    ],
  },
  validating_seed: {
    en: [
      "Checking the site address",
      "Making sure the address is public and safe to open.",
    ],
    id: [
      "Memeriksa alamat situs",
      "Memastikan alamat dapat diakses publik dan aman untuk dibuka.",
    ],
  },
  launching_browser: {
    en: [
      "Opening a secure browser",
      "Starting an isolated browser with a fixed time limit.",
    ],
    id: [
      "Membuka browser aman",
      "Menjalankan browser terisolasi dengan batas waktu tetap.",
    ],
  },
  initializing_case: {
    en: [
      "Creating the case",
      "Saving the target, collection limits, and investigation scope.",
    ],
    id: [
      "Membuat kasus",
      "Menyimpan target, batas pengumpulan, dan ruang lingkup investigasi.",
    ],
  },
  capturing_page: {
    en: [
      "Waiting for the page to load",
      "Letting visible content finish loading before it is captured.",
    ],
    id: [
      "Menunggu halaman selesai dimuat",
      "Memberi waktu agar konten terlihat lengkap sebelum disimpan.",
    ],
  },
  preserving_artifacts: {
    en: [
      "Saving the original page",
      "Saving screenshots, visible text, HTML, and response details.",
    ],
    id: [
      "Menyimpan halaman asli",
      "Menyimpan screenshot, teks terlihat, HTML, dan detail respons.",
    ],
  },
  page_preview_ready: {
    en: [
      "Page preview is ready",
      "A saved screenshot is now available in the preview.",
    ],
    id: [
      "Pratinjau halaman siap",
      "Screenshot yang sudah tersimpan kini tampil di pratinjau.",
    ],
  },
  running_ocr: {
    en: [
      "Reading text from the screenshot",
      "Checking visible image text as additional evidence.",
    ],
    id: [
      "Membaca teks dari screenshot",
      "Memeriksa teks pada gambar sebagai temuan tambahan.",
    ],
  },
  extracting_evidence: {
    en: [
      "Looking for useful findings",
      "Finding public contacts, payments, offers, links, and claims.",
    ],
    id: [
      "Mencari temuan penting",
      "Mencari kontak, pembayaran, promosi, tautan, dan klaim publik.",
    ],
  },
  page_completed: {
    en: [
      "Page saved",
      "The page and its findings have been added to this case.",
    ],
    id: [
      "Halaman sudah disimpan",
      "Halaman dan temuannya sudah ditambahkan ke kasus ini.",
    ],
  },
  generating_candidates: {
    en: [
      "Comparing related findings",
      "Finding possible connections that still need human review.",
    ],
    id: [
      "Membandingkan temuan terkait",
      "Mencari kemungkinan hubungan yang masih perlu ditinjau manusia.",
    ],
  },
  finalizing_case: {
    en: [
      "Packing the evidence",
      "Writing the case manifest and recording capture limitations.",
    ],
    id: [
      "Merapikan paket bukti",
      "Menyusun manifest kasus dan mencatat batas hasil pengumpulan.",
    ],
  },
  verifying_evidence: {
    en: [
      "Checking saved files",
      "Making sure the collected files are complete before exploration.",
    ],
    id: [
      "Memeriksa file yang tersimpan",
      "Memastikan hasil pengumpulan lengkap sebelum penelusuran.",
    ],
  },
  evidence_verified: {
    en: [
      "Saved evidence passed checks",
      "The manifest and artifact hashes match the saved files.",
    ],
    id: [
      "Bukti tersimpan lolos pemeriksaan",
      "Manifest dan hash artefak cocok dengan file yang disimpan.",
    ],
  },
  running_agent: {
    en: [
      "Choosing the next safe step",
      "The model or fallback selects only read-only actions allowed by the server.",
    ],
    id: [
      "Memilih langkah aman berikutnya",
      "Model atau fallback hanya memilih aksi baca yang diizinkan server.",
    ],
  },
  agent_focus_ready: {
    en: [
      "A safe control was selected",
      "The target was checked again before the browser action.",
    ],
    id: [
      "Kontrol aman dipilih",
      "Target diperiksa kembali sebelum aksi browser dijalankan.",
    ],
  },
  interaction_preview_ready: {
    en: [
      "The next page state was saved",
      "The read-only action result and screenshot are now preserved.",
    ],
    id: [
      "Tampilan setelah aksi sudah disimpan",
      "Hasil aksi baca dan screenshot kini telah disimpan.",
    ],
  },
  agent_observations_ready: {
    en: [
      "New page state checked",
      "Visible findings were checked again after the safe action.",
    ],
    id: [
      "Tampilan baru sudah diperiksa",
      "Temuan yang terlihat diperiksa kembali setelah aksi aman.",
    ],
  },
  agent_focus_blocked: {
    en: [
      "Action was not allowed",
      "The action was stopped safely and no successful result is claimed.",
    ],
    id: [
      "Aksi tidak dapat dijalankan",
      "Aksi dihentikan dengan aman dan tidak dianggap berhasil.",
    ],
  },
  classifying_indicators: {
    en: [
      "Grouping gambling indicators",
      "Counting evidence-backed indicators without producing a verdict.",
    ],
    id: [
      "Mengelompokkan indikasi judi online",
      "Menghitung indikator berbasis temuan tanpa membuat putusan.",
    ],
  },
  building_graph: {
    en: [
      "Building the investigation graph",
      "Connecting saved pages, findings, leads, and actions in one view.",
    ],
    id: [
      "Menyusun graph investigasi",
      "Menghubungkan halaman, temuan, kandidat, dan aksi dalam satu tampilan.",
    ],
  },
  completed: {
    en: [
      "Investigation is ready",
      "The graph, screenshots, findings, and timeline are ready to review.",
    ],
    id: [
      "Investigasi siap ditinjau",
      "Graph, screenshot, temuan, dan timeline sudah siap diperiksa.",
    ],
  },
  failed: {
    en: [
      "Investigation stopped",
      "Nothing incomplete is presented as a successful capture.",
    ],
    id: [
      "Investigasi dihentikan",
      "Hasil yang belum lengkap tidak ditampilkan sebagai pengumpulan yang berhasil.",
    ],
  },
}

const scanText = {
  en: {
    siteProcessing: "Website being processed",
    currentPhase: "Current step",
    noPreview: "No page preview is available",
    noPreviewDetail:
      "The process stopped before a valid screenshot could be saved.",
    waitingPreview: "Waiting for the first page preview",
    waitingPreviewDetail:
      "The screenshot will appear here after it has been saved.",
    captureStopped: "Capture stopped",
    evidenceSaved: "Evidence saved",
    active: "Investigation active",
    pages: "Pages saved",
    queued: "waiting",
    observations: "Findings",
    extractor: "Read from saved evidence",
    elapsed: "Time elapsed",
    timing: "Collection and exploration",
    pipeline: "Current step",
    loading: "Loading",
    stopped: "Stopped",
    completed: "Done",
    inProgress: "In progress",
    pending: "Waiting",
    openWorkspace: "Open investigation results",
    returnForm: "Start another investigation",
    activity: "Investigation activity",
    activityHint: "Saved updates from the current process",
    captured: "Complete",
    live: "Running",
    waitingActivity: "Waiting for the first update…",
    technicalProgress: "Technical details",
    browserPending: "Browser is waiting to start",
    boundaryTitle: "Safe collection is active.",
    boundaryBody:
      "HAWK-EYE will not sign in, submit forms, send messages, purchase, or bypass access controls.",
    unavailable: "Investigation cannot be opened",
    unavailableBody:
      "The latest status could not be loaded. Check the connection and try again.",
    returnCases: "Return to cases",
    viewLatest: "Follow latest",
    pageFallback: "Captured public page",
    previewGroup: "Saved page previews",
  },
  id: {
    siteProcessing: "Situs yang sedang diproses",
    currentPhase: "Langkah sekarang",
    noPreview: "Pratinjau halaman belum tersedia",
    noPreviewDetail:
      "Proses berhenti sebelum screenshot yang valid sempat disimpan.",
    waitingPreview: "Menunggu pratinjau halaman pertama",
    waitingPreviewDetail:
      "Screenshot akan muncul di sini setelah berhasil disimpan.",
    captureStopped: "Pengumpulan dihentikan",
    evidenceSaved: "Bukti sudah disimpan",
    active: "Investigasi sedang berjalan",
    pages: "Halaman tersimpan",
    queued: "menunggu",
    observations: "Temuan",
    extractor: "Dibaca dari bukti tersimpan",
    elapsed: "Waktu berjalan",
    timing: "Pengumpulan dan penelusuran",
    pipeline: "Langkah proses",
    loading: "Memuat",
    stopped: "Dihentikan",
    completed: "Selesai",
    inProgress: "Sedang berjalan",
    pending: "Menunggu",
    openWorkspace: "Buka hasil investigasi",
    returnForm: "Mulai investigasi lain",
    activity: "Aktivitas investigasi",
    activityHint: "Pembaruan yang tersimpan dari proses ini",
    captured: "Selesai",
    live: "Berjalan",
    waitingActivity: "Menunggu pembaruan pertama…",
    technicalProgress: "Detail teknis",
    browserPending: "Browser menunggu untuk dijalankan",
    boundaryTitle: "Pengumpulan aman sedang aktif.",
    boundaryBody:
      "HAWK-EYE tidak akan login, mengirim formulir atau pesan, melakukan pembelian, maupun melewati pembatasan akses.",
    unavailable: "Investigasi tidak dapat dibuka",
    unavailableBody:
      "Status terbaru tidak berhasil dimuat. Periksa koneksi lalu coba lagi.",
    returnCases: "Kembali ke daftar kasus",
    viewLatest: "Ikuti yang terbaru",
    pageFallback: "Halaman publik yang tersimpan",
    previewGroup: "Pratinjau halaman tersimpan",
  },
} satisfies Record<Language, Record<string, string>>

function localizedStageCopy(stage: string | undefined, language: Language) {
  return (
    stageCopy[stage ?? "queued"]?.[language] ?? [
      titleCase(stage),
      language === "id"
        ? "Mencatat perkembangan proses saat ini."
        : "Recording the current process update.",
    ]
  )
}

function friendlyFailure(error: string | null | undefined, language: Language) {
  const message = error?.toLowerCase() ?? ""
  if (/timeout|timed out|deadline/.test(message)) {
    return language === "id"
      ? "Situs terlalu lama merespons. Coba lagi atau periksa koneksi VPN."
      : "The site took too long to respond. Try again or check the VPN connection."
  }
  if (/dns|name.*resolv|err_name_not_resolved/.test(message)) {
    return language === "id"
      ? "Alamat situs tidak berhasil ditemukan oleh jaringan."
      : "The site address could not be found by the network."
  }
  if (/blocked|policy|private network|not allowed/.test(message)) {
    return language === "id"
      ? "Alamat atau aksi ini dihentikan oleh batas keamanan HAWK-EYE."
      : "This address or action was stopped by HAWK-EYE's safety boundary."
  }
  if (/browser|chromium|executable/.test(message)) {
    return language === "id"
      ? "Browser pengumpulan tidak dapat dijalankan. Periksa instalasi Chromium."
      : "The collection browser could not start. Check the Chromium installation."
  }
  return language === "id"
    ? "Investigasi berhenti sebelum selesai. Tidak ada hasil yang belum lengkap dianggap berhasil."
    : "The investigation stopped before completion. No incomplete result is treated as successful."
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

function previewTitle(preview: JobPreview, language: Language): string {
  if (preview.kind === "agent_before")
    return language === "id" ? "Sebelum aksi aman" : "Before safe action"
  if (preview.kind === "agent_after")
    return language === "id" ? "Setelah aksi aman" : "After safe action"
  return preview.page_id.replace(
    "page-",
    language === "id" ? "Halaman " : "Page "
  )
}

interface ProcessedSite {
  title: string
  hostname: string
}

function processedSite(
  job: InvestigationJob | undefined,
  language: Language
): ProcessedSite {
  const sourceCase = job?.result?.source_case
  const url =
    job?.target?.final_url ||
    job?.visual_state?.latest_preview?.url ||
    sourceCase?.final_url_display ||
    job?.target?.seed_url ||
    job?.result?.seed_url ||
    ""
  const hostname = url
    ? hostnameFrom(url)
    : language === "id"
      ? "Menyiapkan target"
      : "Preparing target"
  const title =
    job?.target?.page_title?.trim() ||
    sourceCase?.page_title?.trim() ||
    hostname

  return { title, hostname }
}

function ScanVisual({
  job,
  site,
  language,
}: {
  job?: InvestigationJob
  site: ProcessedSite
  language: Language
}) {
  const text = scanText[language]
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
              <b>{previewTitle(selected, language)}</b>
            </span>
            <Badge
              className={cn(
                "preview-verification",
                selected.verification === "verified" && "status-success",
                selected.verification === "persisted" && "status-cyan"
              )}
            >
              {selected.verification === "verified"
                ? language === "id"
                  ? "BUKTI TERVERIFIKASI"
                  : "VERIFIED EVIDENCE"
                : selected.verification === "persisted"
                  ? language === "id"
                    ? "AKSI TERSIMPAN"
                    : "PERSISTED ACTION"
                  : language === "id"
                    ? "PRATINJAU · MENUNGGU VERIFIKASI"
                    : "PREVIEW · VERIFICATION PENDING"}
            </Badge>
            {selected.revision !== latest?.revision ? (
              <button
                className="preview-follow"
                type="button"
                onClick={() => setSelectedRevision(null)}
              >
                {text.viewLatest}
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
              alt={`${language === "id" ? "Pratinjau halaman publik" : "Captured public page preview"}: ${previewTitle(selected, language)}`}
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
              {selected.url || text.pageFallback}
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
                    ? language === "id"
                      ? "Kontrol publik yang aman dipilih"
                      : "A safe public control was selected"
                    : focus.status === "evidence_extracted"
                      ? (focus.added_observation_count ?? 0) > 0
                        ? language === "id"
                          ? "Temuan publik baru dibaca"
                          : "New public findings were extracted"
                        : language === "id"
                          ? "Pemeriksaan setelah aksi selesai"
                          : "Post-action check completed"
                      : focus.status === "blocked"
                        ? language === "id"
                          ? "Aksi aman dihentikan"
                          : "Safe action stopped"
                        : language === "id"
                          ? "Aksi baca selesai"
                          : "Read-only action completed"}
                </b>
                <p>
                  {focus.label ||
                    (language === "id"
                      ? "Kontrol informasi publik"
                      : "Public information control")}
                  {focus.status === "blocked" && focus.reason
                    ? ` · ${focus.reason}`
                    : (focus.added_observation_count ?? 0) > 0
                      ? language === "id"
                        ? ` · ${focus.added_observation_count} temuan baru`
                        : ` · ${focus.added_observation_count} new findings`
                      : focus.status === "evidence_extracted"
                        ? language === "id"
                          ? " · tidak ada temuan baru"
                          : " · no new findings"
                        : ""}
                </p>
                <small>
                  {focus.tool_name ||
                    (language === "id"
                      ? "Aksi dibatasi kebijakan"
                      : "Policy-gated action")}
                </small>
              </div>
            </div>
          ) : null}
          {previews.length > 1 ? (
            <div
              className="preview-thumbnails"
              role="group"
              aria-label={text.previewGroup}
            >
              {previews.slice(-6).map((preview) => (
                <button
                  key={preview.revision}
                  type="button"
                  className={cn(
                    preview.revision === selected.revision && "preview-selected"
                  )}
                  onClick={() => setSelectedRevision(preview.revision)}
                  aria-label={`${language === "id" ? "Tampilkan" : "Show"} ${previewTitle(preview, language)}`}
                  aria-pressed={preview.revision === selected.revision}
                >
                  <img
                    src={jobPreviewUrl(job!.job_id, preview.revision, true)}
                    alt=""
                    loading="lazy"
                    decoding="async"
                  />
                  <span>{previewTitle(preview, language)}</span>
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
            <span>{text.siteProcessing}</span>
            <strong>{site.title}</strong>
            {site.hostname !== site.title ? (
              <small>{site.hostname}</small>
            ) : null}
          </div>
          <b>
            {job?.status === "failed" ? text.noPreview : text.waitingPreview}
          </b>
          <p>
            {job?.status === "failed"
              ? text.noPreviewDetail
              : text.waitingPreviewDetail}
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
          ? text.captureStopped
          : job?.status === "completed"
            ? text.evidenceSaved
            : text.active}
      </Badge>
    </div>
  )
}

export function ScanPage() {
  const { jobId } = useParams<{ jobId: string }>()
  const navigate = useNavigate()
  const [now, setNow] = useState(() => Date.now())
  const [language, setLanguage] = useState<Language>(() =>
    window.localStorage.getItem("hawk-eye-language") === "id" ? "id" : "en"
  )
  const notificationRef = useRef<string | null>(null)
  const text = scanText[language]
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
  const site = processedSite(job, language)
  const failureMessage = friendlyFailure(job?.error, language)

  useEffect(() => {
    document.documentElement.lang = language
  }, [language])

  useEffect(() => {
    if (!job || job.status !== "failed") return
    const notificationId = `${job.job_id}:failed:${language}`
    if (notificationRef.current === notificationId) return
    notificationRef.current = notificationId
    toast.error(
      language === "id" ? "Investigasi dihentikan" : "Investigation stopped",
      {
        id: `scan-failed-${job.job_id}`,
        description: friendlyFailure(job.error, language),
        duration: 12_000,
        action: {
          label: language === "id" ? "Kembali" : "Go back",
          onClick: () => navigate("/"),
        },
      }
    )
  }, [job, language, navigate])

  useEffect(() => {
    if (!jobQuery.isError) return
    toast.error(
      language === "id"
        ? "Status investigasi tidak dapat dimuat"
        : "Investigation status could not be loaded",
      {
        id: `scan-query-error-${jobId}`,
        description: text.unavailableBody,
        duration: 10_000,
      }
    )
  }, [jobId, jobQuery.isError, language, text.unavailableBody])

  const toggleLanguage = () => {
    setLanguage((current) => {
      const next = current === "en" ? "id" : "en"
      window.localStorage.setItem("hawk-eye-language", next)
      return next
    })
  }
  const elapsedAt = jobIsActive
    ? now
    : job?.updated_at
      ? new Date(job.updated_at).getTime()
      : now
  const groupIndex = job ? currentGroup(job) : 0
  const [phaseTitle, phaseCopy] = localizedStageCopy(job?.stage, language)
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
        <AppHeader
          context="scan"
          language={language}
          onLanguageToggle={toggleLanguage}
        />
        <main className="scan-error">
          <Warning weight="duotone" />
          <h1>{text.unavailable}</h1>
          <p>{text.unavailableBody}</p>
          <Button onClick={() => navigate("/")}>{text.returnCases}</Button>
        </main>
      </div>
    )
  }

  return (
    <div className="app-page scan-page">
      <AppHeader
        context="scan"
        language={language}
        onLanguageToggle={toggleLanguage}
      />
      <main className="scan-main-page">
        <section
          className={cn(
            "scan-console",
            job?.status === "failed" && "scan-console-failed",
            job?.status === "completed" && "scan-console-complete"
          )}
        >
          <ScanVisual job={job} site={site} language={language} />

          <div className="scan-progress-panel">
            <div className="scan-target-summary" aria-live="polite">
              <span className="scan-target-icon">
                <Browser weight="duotone" />
              </span>
              <div>
                <span>{text.siteProcessing}</span>
                <strong>{site.title}</strong>
                {site.hostname !== site.title ? (
                  <small>{site.hostname}</small>
                ) : null}
              </div>
            </div>
            <header className="scan-phase-heading">
              <div>
                <p className="eyebrow">{text.currentPhase}</p>
                <h1 aria-live="polite">{phaseTitle}</h1>
                <p>{job?.status === "failed" ? failureMessage : phaseCopy}</p>
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
                <p>{text.pages}</p>
                <small>
                  {queue ?? "—"} {text.queued}
                </small>
              </article>
              <article>
                <span>
                  <Binoculars weight="duotone" />
                </span>
                <strong>{evidence ?? "—"}</strong>
                <p>{text.observations}</p>
                <small>{text.extractor}</small>
              </article>
              <article>
                <span>
                  <Clock weight="duotone" />
                </span>
                <strong>{formatElapsed(job?.started_at, elapsedAt)}</strong>
                <p>{text.elapsed}</p>
                <small>{text.timing}</small>
              </article>
              <article>
                <span>
                  <Database weight="duotone" />
                </span>
                <strong>
                  {groupIndex + 1} / {stageGroups.length}
                </strong>
                <p>{text.pipeline}</p>
                <small>
                  {job?.stage
                    ? localizedStageCopy(job.stage, language)[0]
                    : text.loading}
                </small>
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
                    key={group.label.en}
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
                    <strong>{group.label[language]}</strong>
                    <small>
                      {failed
                        ? text.stopped
                        : reached
                          ? text.completed
                          : active
                            ? text.inProgress
                            : text.pending}
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
                {text.openWorkspace} <ArrowRight weight="bold" />
              </Button>
            ) : null}
            {job?.status === "failed" ? (
              <Button
                className="open-workspace-button"
                variant="outline"
                size="lg"
                onClick={() => navigate("/")}
              >
                {text.returnForm}
              </Button>
            ) : null}
          </div>
        </section>

        <section className="activity-console">
          <header>
            <div className="activity-heading">
              <span className="activity-heading-icon">
                <Pulse weight="fill" />
              </span>
              <span>
                <strong>{text.activity}</strong>
                <small>{text.activityHint}</small>
              </span>
            </div>
            <Badge variant="outline" aria-live="polite">
              <span
                className={cn("live-dot", !jobIsActive && "live-dot-static")}
              />{" "}
              {job?.status === "completed"
                ? text.captured
                : job?.status === "failed"
                  ? text.stopped
                  : text.live}
            </Badge>
          </header>
          <ScrollArea className="activity-scroll">
            <div className="activity-list" aria-live="polite">
              {history.length ? (
                history.map((entry, index) => {
                  const Icon = stageIcon(entry.stage)
                  const [label, copy] = localizedStageCopy(
                    entry.stage,
                    language
                  )
                  return (
                    <article
                      key={`${entry.stage}:${entry.at}:${index}`}
                      className={cn(
                        "activity-row",
                        index === history.length - 1 && "activity-row-latest",
                        entry.stage === "failed" && "activity-row-failed"
                      )}
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
                  <SpinnerGap className="animate-spin" /> {text.waitingActivity}
                </article>
              )}
            </div>
          </ScrollArea>
        </section>

        <section className="technical-strip">
          <span className="technical-label">
            <Code weight="duotone" /> {text.technicalProgress}
          </span>
          <div>
            {history.slice(-8).map((entry, index) => (
              <span key={`${entry.stage}:${index}`}>
                <i /> {localizedStageCopy(entry.stage, language)[0]}{" "}
                <time>{formatTime(entry.at)}</time>
              </span>
            ))}
            {!history.length ? (
              <span>
                <i /> {text.browserPending}
              </span>
            ) : null}
          </div>
          <HardDrives weight="duotone" />
        </section>

        <aside className="scan-boundary">
          <ShieldCheck weight="duotone" />
          <span>
            <b>{text.boundaryTitle}</b> {text.boundaryBody}
          </span>
          <Sparkle weight="duotone" />
        </aside>
      </main>
    </div>
  )
}
