import { ArrowSquareOut, Plus, Pulse } from "@phosphor-icons/react"
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
}: {
  currentValue?: string
  context?: "landing" | "scan" | "workspace" | "summary"
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

      <div className="header-signal" aria-hidden="true">
        <span />
        <b>PUBLIC EVIDENCE INSTRUMENT</b>
        <span />
      </div>

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
        <div className="header-mode">
          <Pulse weight="fill" />
          {context === "scan" ? "CAPTURE CHANNEL ACTIVE" : "LOCAL · READ ONLY"}
        </div>
      )}

      <Tooltip>
        <TooltipTrigger
          render={
            <Button
              className="header-action"
              onClick={() => navigate("/")}
              variant={context === "landing" ? "default" : "outline"}
            >
              <Plus weight="bold" />
              New investigation
              {context === "landing" ? null : <ArrowSquareOut />}
            </Button>
          }
        />
        <TooltipContent>
          Start a new bounded public investigation
        </TooltipContent>
      </Tooltip>
    </header>
  )
}
