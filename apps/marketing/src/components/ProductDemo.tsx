import { EvidenceGraph } from "@hawkeye/graph";
import { Button } from "@hawkeye/ui";
import {
  ArrowCounterClockwiseIcon,
  PauseIcon,
  PlayIcon,
} from "@phosphor-icons/react";
import { useEffect, useState, type ChangeEvent } from "react";

const events = [
  {
    step: 1,
    time: "00:04",
    title: "Capture preserved",
    detail: "Rendered /Contact and its immutable screenshot were stored.",
  },
  {
    step: 2,
    time: "00:08",
    title: "Entities extracted",
    detail: "Telegram, phone, and WhatsApp identifiers were observed.",
  },
  {
    step: 3,
    time: "00:11",
    title: "Relationship verified",
    detail: "Observed entities were linked back to the captured page.",
  },
  {
    step: 4,
    time: "00:14",
    title: "Candidate proposed",
    detail: "qq101uok.net remains a pending lead for human review.",
  },
];

export function ProductDemo() {
  const [step, setStep] = useState(1);
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState(1);

  useEffect(() => {
    if (!playing) return;
    const timer = window.setInterval(() => {
      setStep((value) => (value >= 4 ? 1 : value + 1));
    }, 1800 / speed);
    return () => window.clearInterval(timer);
  }, [playing, speed]);

  const current = events[step - 1];
  return (
    <div className="replay-demo">
      <EvidenceGraph visibleStep={step} compact />
      <div className="replay-console">
        <div className="replay-console__controls">
          <Button
            variant="outline"
            onClick={() => {
              setStep(1);
              setPlaying(true);
            }}
            aria-label="Replay investigation"
          >
            <ArrowCounterClockwiseIcon /> Replay
          </Button>
          <Button
            variant="ghost"
            onClick={() => setPlaying((value) => !value)}
            aria-label={playing ? "Pause replay" : "Play replay"}
          >
            {playing ? (
              <>
                <PauseIcon /> Pause
              </>
            ) : (
              <>
                <PlayIcon /> Play
              </>
            )}
          </Button>
          <label>
            Speed
            <select
              className="he-select"
              value={speed}
              onChange={(event: ChangeEvent<HTMLSelectElement>) =>
                setSpeed(Number(event.target.value))
              }
              aria-label="Replay speed"
            >
              <option value="0.5">0.5×</option>
              <option value="1">1×</option>
              <option value="2">2×</option>
            </select>
          </label>
        </div>
        <div className="replay-console__event" aria-live="polite">
          <span>{current.time}</span>
          <div>
            <strong>{current.title}</strong>
            <p>{current.detail}</p>
          </div>
        </div>
        <input
          className="replay-range"
          type="range"
          min="1"
          max="4"
          value={step}
          onChange={(event) => {
            setPlaying(false);
            setStep(Number(event.target.value));
          }}
          aria-label="Investigation timeline"
        />
        <ol className="replay-steps">
          {events.map((event) => (
            <li key={event.step} data-active={event.step <= step}>
              <button
                type="button"
                onClick={() => {
                  setPlaying(false);
                  setStep(event.step);
                }}
                aria-label={`Go to ${event.title}`}
              >
                <i />
                {event.title}
              </button>
            </li>
          ))}
        </ol>
      </div>
    </div>
  );
}
