import { Pause, Play, Rewind } from "@phosphor-icons/react"
import { useEffect, useRef, useState } from "react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import type { TimelineItem } from "@/lib/graph"
import { timelinePresentation } from "@/lib/graph"
import { exactTime, formatTime } from "@/lib/format"
import { cn } from "@/lib/utils"

export function InvestigationTimeline({
  timeline,
  activeIndex,
  onSelect,
  live = false,
}: {
  timeline: TimelineItem[]
  activeIndex: number
  onSelect: (index: number) => void
  live?: boolean
}) {
  const [playing, setPlaying] = useState(false)
  const [speed, setSpeed] = useState(650)
  const trackRef = useRef<HTMLDivElement>(null)
  const reduceMotion = window.matchMedia(
    "(prefers-reduced-motion: reduce)"
  ).matches

  useEffect(() => {
    if (!playing || reduceMotion || !timeline.length) return
    if (activeIndex >= timeline.length - 1) {
      const stopTimer = window.setTimeout(() => setPlaying(false), 0)
      return () => window.clearTimeout(stopTimer)
    }
    const timer = window.setTimeout(() => onSelect(activeIndex + 1), speed)
    return () => window.clearTimeout(timer)
  }, [activeIndex, onSelect, playing, reduceMotion, speed, timeline.length])

  useEffect(() => {
    const card = trackRef.current?.querySelector(
      `[data-index="${activeIndex}"]`
    )
    card?.scrollIntoView({
      block: "nearest",
      inline: "nearest",
      behavior: reduceMotion ? "auto" : "smooth",
    })
  }, [activeIndex, reduceMotion])

  const replay = () => {
    if (!timeline.length) return
    onSelect(0)
    if (!reduceMotion) setPlaying(true)
  }

  const mode = live
    ? "LIVE"
    : activeIndex >= timeline.length - 1
      ? "REPLAY"
      : "CAPTURED"
  const current = timeline[activeIndex]

  return (
    <section className="timeline-panel" aria-label="Capture and event timeline">
      <div className="timeline-transport">
        <Button variant="outline" onClick={replay}>
          <Rewind weight="bold" />
          Replay
        </Button>
        <Button
          size="icon"
          variant="outline"
          aria-label={playing ? "Pause timeline" : "Play timeline"}
          onClick={() => setPlaying((value) => !value)}
          disabled={!timeline.length}
        >
          {playing ? <Pause weight="fill" /> : <Play weight="fill" />}
        </Button>
        <label>
          <span>Speed</span>
          <input
            type="range"
            min="180"
            max="1400"
            step="10"
            value={speed}
            onChange={(event) => setSpeed(Number(event.target.value))}
            aria-label="Replay speed"
          />
        </label>
        <Badge className={cn("timeline-mode", live && "timeline-mode-live")}>
          {mode}
        </Badge>
      </div>

      <div className="timeline-navigation">
        <div ref={trackRef} className="timeline-track">
          {timeline.map((item, index) => {
            const presentation = timelinePresentation(item)
            return (
              <button
                key={`${item.sequence}:${item.label}`}
                type="button"
                data-index={index}
                className={cn(
                  "timeline-card",
                  activeIndex === index && "timeline-card-active"
                )}
                style={
                  { "--event-color": presentation.color } as React.CSSProperties
                }
                aria-current={activeIndex === index ? "step" : undefined}
                onClick={() => {
                  setPlaying(false)
                  onSelect(index)
                }}
                title={exactTime(item.occurredAt)}
              >
                <span className="timeline-icon">{presentation.icon}</span>
                <span className="timeline-copy">
                  <b>{item.label}</b>
                  <small>{item.detail}</small>
                </span>
                <time dateTime={item.occurredAt ?? undefined}>
                  {formatTime(item.occurredAt)}
                </time>
              </button>
            )
          })}
        </div>
        <div className="timeline-scrubber">
          <input
            type="range"
            min="0"
            max={Math.max(0, timeline.length - 1)}
            value={Math.max(0, activeIndex)}
            disabled={!timeline.length}
            aria-label="Timeline position"
            onChange={(event) => {
              setPlaying(false)
              onSelect(Number(event.target.value))
            }}
          />
          <time title={exactTime(current?.occurredAt)}>
            {formatTime(current?.occurredAt)}
          </time>
        </div>
      </div>
    </section>
  )
}
