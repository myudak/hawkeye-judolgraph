import {
  BrowserIcon,
  CheckCircleIcon,
  CursorClickIcon,
  EyeIcon,
  ShieldCheckIcon,
  SparkleIcon,
} from "@phosphor-icons/react";
import { useEffect, useState } from "react";
import { localize, useMarketingLanguage } from "../lib/language";

const phases = [
  {
    label: { id: "Membaca konteks", en: "Reading context" },
    detail: {
      id: "Teks dan tautan publik dinormalisasi.",
      en: "Public text and links are normalized.",
    },
    target: "contact",
    icon: EyeIcon,
  },
  {
    label: { id: "Memilih aksi aman", en: "Selecting a safe action" },
    detail: {
      id: "Agen memilih referensi /contact dari server.",
      en: "The agent selects the server-issued /contact reference.",
    },
    target: "contact",
    icon: CursorClickIcon,
  },
  {
    label: { id: "Membuka halaman publik", en: "Opening a public page" },
    detail: {
      id: "Navigasi dibatasi kebijakan dan anggaran waktu.",
      en: "Navigation stays inside policy and time budgets.",
    },
    target: "route",
    icon: BrowserIcon,
  },
  {
    label: { id: "Menyimpan bukti", en: "Preserving evidence" },
    detail: {
      id: "Screenshot dan observasi ditautkan ke sumber.",
      en: "Screenshot and observations are linked to their source.",
    },
    target: "evidence",
    icon: ShieldCheckIcon,
  },
] as const;

export function AgentBrowserDemo() {
  const [phase, setPhase] = useState(0);
  const language = useMarketingLanguage();

  useEffect(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const timer = window.setInterval(
      () => setPhase((current) => (current + 1) % phases.length),
      2100,
    );
    return () => window.clearInterval(timer);
  }, []);

  const current = phases[phase];
  const Icon = current.icon;

  return (
    <div className="agent-browser" data-agent-target={current.target}>
      <div className="agent-browser__chrome">
        <span />
        <span />
        <span />
        <div>
          <ShieldCheckIcon aria-hidden="true" />
          https://example-investigation.test
        </div>
        <small>
          <i /> {localize(language, { id: "TERBATAS", en: "BOUNDED" })}
        </small>
      </div>
      <div className="agent-browser__viewport">
        <div className="agent-browser__site-nav">
          <strong>PUBLIC SITE</strong>
          <button type="button">Home</button>
          <button type="button" data-agent-element="contact">
            {localize(language, { id: "Hubungi kami", en: "Contact us" })}
          </button>
          <button type="button">FAQ</button>
        </div>
        <div className="agent-browser__mock-copy">
          <span />
          <span />
          <span />
          <strong>
            {localize(language, {
              id: "Informasi publik yang dapat diamati",
              en: "Observable public information",
            })}
          </strong>
          <p>
            {localize(language, {
              id: "Agen hanya berinteraksi dengan target yang sudah dinyatakan aman oleh server.",
              en: "The agent interacts only with targets already marked safe by the server.",
            })}
          </p>
        </div>
        <div className="agent-browser__route" data-agent-element="route">
          <BrowserIcon aria-hidden="true" /> /contact
          <span>GET · 200</span>
        </div>
        <div className="agent-browser__evidence" data-agent-element="evidence">
          <CheckCircleIcon aria-hidden="true" />
          <div>
            <strong>
              {localize(language, {
                id: "Observasi tersimpan",
                en: "Observation preserved",
              })}
            </strong>
            <span>public_contact · +63 915…0101</span>
          </div>
        </div>
        <div className="agent-browser__cursor" aria-hidden="true">
          <CursorClickIcon weight="fill" />
          <span>HAWK-EYE AGENT</span>
        </div>
        <div className="agent-browser__scan" aria-hidden="true" />
      </div>
      <div className="agent-browser__status" aria-live="polite">
        <div className="agent-browser__status-icon">
          <Icon aria-hidden="true" />
        </div>
        <div>
          <span>
            {localize(language, { id: "LANGKAH AGEN", en: "AGENT STEP" })}{" "}
            {phase + 1}/{phases.length}
          </span>
          <strong>{localize(language, current.label)}</strong>
          <p>{localize(language, current.detail)}</p>
        </div>
        <SparkleIcon className="agent-browser__sparkle" aria-hidden="true" />
      </div>
    </div>
  );
}
