import { ArrowSquareOut, Plus, Translate } from "@phosphor-icons/react"
import { useNavigate } from "react-router-dom"

import { Button } from "@/components/ui/button"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import { hostnameFrom, titleCase } from "@/lib/format"
import { useIndexes } from "@/hooks/use-indexes"
import { BrandLockup } from "@/components/brand-mark"

export function AppHeader({
  currentValue,
  context,
  language = "en",
  onLanguageToggle,
}: {
  currentValue?: string
  context?: "landing" | "scan" | "workspace" | "summary"
  language?: "en" | "id"
  onLanguageToggle?: () => void
}) {
  const navigate = useNavigate()
  const { cases, runs } = useIndexes()

  const openEvidence = (value: string | null) => {
    if (!value) return
    const split = value.indexOf(":")
    if (split < 0) return
    const kind = value.slice(0, split)
    const id = value.slice(split + 1)
    if ((kind === "case" || kind === "run") && id)
      navigate(`/workspace/${kind}/${id}`)
  }

  return (
    <header className="app-header">
      <button
        className="brand-button"
        type="button"
        onClick={() => navigate("/")}
      >
        <BrandLockup />
      </button>

      {context === "workspace" || context === "summary" ? (
        <Select value={currentValue} onValueChange={openEvidence}>
          <SelectTrigger
            className="header-case-select"
            aria-label="Open saved evidence"
          >
            <SelectValue placeholder="Select saved evidence" />
          </SelectTrigger>
          <SelectContent>
            {runs.map((run) => (
              <SelectItem
                key={run.workspace_id}
                value={`run:${run.workspace_id}`}
              >
                {hostnameFrom(run.seed_url || run.case_id)} ·{" "}
                {titleCase(run.lead_status)}
              </SelectItem>
            ))}
            {cases
              .filter((item) => item.integrity === "verified")
              .map((item) => (
                <SelectItem key={item.case_id} value={`case:${item.case_id}`}>
                  {hostnameFrom(item.final_url_display)} ·{" "}
                  {titleCase(item.capture_adequacy)}
                </SelectItem>
              ))}
          </SelectContent>
        </Select>
      ) : (
        <span className="header-spacer" aria-hidden="true" />
      )}

      <div className="header-actions">
        {onLanguageToggle ? (
          <Button
            className="header-language"
            type="button"
            variant="outline"
            onClick={onLanguageToggle}
            aria-label={
              language === "id"
                ? "Switch to English"
                : "Ganti ke Bahasa Indonesia"
            }
            title={language === "id" ? "Switch to English" : "Bahasa Indonesia"}
          >
            <Translate weight="bold" />
            {language === "id" ? "ID" : "EN"}
          </Button>
        ) : null}

        <Tooltip>
          <TooltipTrigger
            render={
              <Button
                className="header-action"
                onClick={() => navigate("/")}
                variant={context === "landing" ? "default" : "outline"}
              >
                <Plus weight="bold" />
                {language === "id" ? "Investigasi baru" : "New investigation"}
                {context === "landing" ? null : <ArrowSquareOut />}
              </Button>
            }
          />
          <TooltipContent>
            {language === "id"
              ? "Mulai investigasi publik baru yang terkontrol"
              : "Start a new bounded public investigation"}
          </TooltipContent>
        </Tooltip>
      </div>
    </header>
  )
}
