import { useState } from "react"
import { Button } from "@/components/ui/button"

export function DemoGuide({
  language,
  scenarioId,
  onReplay,
  onInspect,
  onSummary,
}: {
  language: "en" | "id"
  scenarioId: string
  onReplay: () => void
  onInspect: () => void
  onSummary: () => void
}) {
  const [step, setStep] = useState(0)
  const [dismissed, setDismissed] = useState(false)
  const related = scenarioId === "demo-related"
  const limited = scenarioId === "demo-restricted"
  const steps =
    language === "id"
      ? [
          {
            title: "Ikuti timeline",
            detail:
              "Putar ulang event contoh. Graph mengikuti bukti yang sudah tersimpan.",
            action: "Mulai timeline",
            run: onReplay,
          },
          {
            title: "Periksa bukti",
            detail: related
              ? "Di tab Bukti, buka kandidat contoh lalu simpan review. Tautan tidak membuktikan kepemilikan."
              : limited
                ? "Periksa screenshot batas akses. Tidak ada observasi yang dibuat dari konten tidak tersedia."
                : "Periksa kontak, screenshot sumber, dan asal-usulnya di tab Bukti.",
            action: "Buka bukti",
            run: onInspect,
          },
          {
            title: "Baca ringkasan",
            detail:
              "Ekspor JSON atau Markdown contoh. Review hanya tersimpan di sesi browser ini.",
            action: "Buka ringkasan",
            run: onSummary,
          },
        ]
      : [
          {
            title: "Follow the timeline",
            detail:
              "Replay the sample events. The graph follows evidence already stored in the fixture.",
            action: "Start timeline",
            run: onReplay,
          },
          {
            title: "Inspect the evidence",
            detail: related
              ? "In Evidence, reveal the sample candidate and save a review. A link does not establish ownership."
              : limited
                ? "Inspect the restriction screenshot. Unavailable content produces no inferred observations."
                : "Inspect the contact, source screenshot, and provenance in the Evidence tab.",
            action: "Open evidence",
            run: onInspect,
          },
          {
            title: "Read the summary",
            detail:
              "Export sample JSON or Markdown. Reviews stay in this browser session.",
            action: "Open summary",
            run: onSummary,
          },
        ]
  if (dismissed)
    return (
      <div className="demo-guide-closed">
        <Button size="sm" variant="ghost" onClick={() => setDismissed(false)}>
          {language === "id" ? "Buka panduan" : "Show guide"}
        </Button>
      </div>
    )
  const current = steps[step]
  return (
    <section
      className="demo-guide"
      aria-label={language === "id" ? "Panduan demo" : "Demo guide"}
    >
      <div aria-live="polite">
        <strong>
          {step + 1}/3 · {current.title}
        </strong>
        <p>{current.detail}</p>
      </div>
      <div className="demo-guide-actions">
        <Button
          size="sm"
          variant="ghost"
          disabled={step === 0}
          onClick={() => setStep(step - 1)}
        >
          {language === "id" ? "Kembali" : "Back"}
        </Button>
        <Button size="sm" onClick={current.run}>
          {current.action}
        </Button>
        {step < 2 ? (
          <Button size="sm" variant="outline" onClick={() => setStep(step + 1)}>
            {language === "id" ? "Lanjut" : "Next"}
          </Button>
        ) : null}
        <Button size="sm" variant="ghost" onClick={() => setDismissed(true)}>
          {language === "id" ? "Tutup" : "Dismiss"}
        </Button>
      </div>
    </section>
  )
}
