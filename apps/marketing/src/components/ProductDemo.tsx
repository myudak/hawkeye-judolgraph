import { EvidenceGraph } from "@hawkeye/graph";
import { Button } from "@hawkeye/ui";
import {
  ArrowCounterClockwiseIcon,
  PauseIcon,
  PlayIcon,
} from "@phosphor-icons/react";
import { useEffect, useState, type ChangeEvent } from "react";
import { localize, useMarketingLanguage } from "../lib/language";

const events = [
  {
    step: 1,
    time: "00:04",
    title: { id: "Tangkapan dipreservasi", en: "Capture preserved" },
    detail: {
      id: "Halaman /Contact dan screenshot yang tidak dapat diubah telah disimpan.",
      en: "Rendered /Contact and its immutable screenshot were stored.",
    },
  },
  {
    step: 2,
    time: "00:08",
    title: { id: "Entitas diekstrak", en: "Entities extracted" },
    detail: {
      id: "Identitas Telegram, telepon, dan WhatsApp ditemukan.",
      en: "Telegram, phone, and WhatsApp identifiers were observed.",
    },
  },
  {
    step: 3,
    time: "00:11",
    title: { id: "Relasi terverifikasi", en: "Relationship verified" },
    detail: {
      id: "Entitas yang ditemukan ditautkan kembali ke halaman sumber.",
      en: "Observed entities were linked back to the captured page.",
    },
  },
  {
    step: 4,
    time: "00:14",
    title: { id: "Kandidat diajukan", en: "Candidate proposed" },
    detail: {
      id: "qq101uok.net tetap menjadi lead tertunda untuk ditinjau manusia.",
      en: "qq101uok.net remains a pending lead for human review.",
    },
  },
];

export function ProductDemo() {
  const language = useMarketingLanguage();
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
            aria-label={localize(language, {
              id: "Ulangi investigasi",
              en: "Replay investigation",
            })}
          >
            <ArrowCounterClockwiseIcon />{" "}
            {localize(language, { id: "Ulangi", en: "Replay" })}
          </Button>
          <Button
            variant="ghost"
            onClick={() => setPlaying((value) => !value)}
            aria-label={
              playing
                ? localize(language, { id: "Jeda replay", en: "Pause replay" })
                : localize(language, { id: "Putar replay", en: "Play replay" })
            }
          >
            {playing ? (
              <>
                <PauseIcon /> {localize(language, { id: "Jeda", en: "Pause" })}
              </>
            ) : (
              <>
                <PlayIcon /> {localize(language, { id: "Putar", en: "Play" })}
              </>
            )}
          </Button>
          <label>
            {localize(language, { id: "Kecepatan", en: "Speed" })}
            <select
              className="he-select"
              value={speed}
              onChange={(event: ChangeEvent<HTMLSelectElement>) =>
                setSpeed(Number(event.target.value))
              }
              aria-label={localize(language, {
                id: "Kecepatan replay",
                en: "Replay speed",
              })}
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
            <strong>{localize(language, current.title)}</strong>
            <p>{localize(language, current.detail)}</p>
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
          aria-label={localize(language, {
            id: "Timeline investigasi",
            en: "Investigation timeline",
          })}
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
                aria-label={`${localize(language, { id: "Buka", en: "Go to" })} ${localize(language, event.title)}`}
              >
                <i />
                {localize(language, event.title)}
              </button>
            </li>
          ))}
        </ol>
      </div>
    </div>
  );
}
