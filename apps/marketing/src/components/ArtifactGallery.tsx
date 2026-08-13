import {
  Badge,
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@hawkeye/ui";
import {
  CheckCircleIcon,
  CodeIcon,
  FileImageIcon,
  FingerprintIcon,
} from "@phosphor-icons/react";
import { useState } from "react";
import { localize, useMarketingLanguage } from "../lib/language";

const artifacts = [
  {
    id: "screenshot",
    index: "01",
    title: { id: "Bukti screenshot", en: "Screenshot evidence" },
    file: "screenshot-contact-full.png",
    hash: "sha256: 7b8f…9a1c",
    icon: <FileImageIcon />,
    summary: {
      id: "Rekaman visual halaman penuh dari rute kontak publik.",
      en: "Full-page visual record of the public contact route.",
    },
  },
  {
    id: "html",
    index: "02",
    title: { id: "Snapshot HTML", en: "HTML snapshot" },
    file: "rendered-contact.html",
    hash: "sha256: 2e40…d7af",
    icon: <CodeIcon />,
    summary: {
      id: "Markup hasil render dipreservasi sebelum ekstraksi.",
      en: "Bounded rendered markup preserved before extraction.",
    },
  },
  {
    id: "observation",
    index: "03",
    title: { id: "Observasi terekstrak", en: "Extracted observation" },
    file: "observation-00042.json",
    hash: "sha256: a6d9…42bc",
    icon: <FingerprintIcon />,
    summary: {
      id: "Identitas publik ternormalisasi dengan referensi sumber yang jelas.",
      en: "Normalized public identifier with explicit source references.",
    },
  },
];

export function ArtifactGallery({ screenshot }: { screenshot: string }) {
  const language = useMarketingLanguage();
  const [selected, setSelected] = useState<(typeof artifacts)[number] | null>(
    null,
  );
  return (
    <>
      <div className="grid overflow-hidden rounded-2xl border border-border bg-card/75 lg:grid-cols-3">
        {artifacts.map((artifact) => (
          <article
            className="border-b border-border p-6 last:border-b-0 lg:border-r lg:border-b-0 lg:last:border-r-0 sm:p-8"
            key={artifact.id}
          >
            <div className="flex items-start justify-between text-xs font-semibold text-[var(--hk-pink)]">
              <span>{artifact.index}</span>
              <i className="flex size-11 items-center justify-center rounded-full bg-[var(--hk-pink)]/8 text-lg not-italic">
                {artifact.icon}
              </i>
            </div>
            <h3 className="mt-10 text-xl font-semibold text-foreground">
              {localize(language, artifact.title)}
            </h3>
            <p className="mt-2 text-sm leading-6 text-muted-foreground">
              {localize(language, artifact.summary)}
            </p>
            <dl className="mt-6 grid gap-3">
              <div>
                <dt className="text-[0.65rem] font-semibold tracking-wide text-muted-foreground uppercase">
                  {localize(language, { id: "Hash file", en: "File hash" })}
                </dt>
                <dd className="mt-1 break-all font-mono text-xs text-foreground">
                  {artifact.hash}
                </dd>
              </div>
              <div>
                <dt className="text-[0.65rem] font-semibold tracking-wide text-muted-foreground uppercase">
                  {localize(language, { id: "Waktu tangkap", en: "Timestamp" })}
                </dt>
                <dd className="mt-1 text-xs text-foreground">
                  12 Aug 2026 · 07:03:13 WIB
                </dd>
              </div>
              <div>
                <dt className="text-[0.65rem] font-semibold tracking-wide text-muted-foreground uppercase">
                  {localize(language, { id: "URL sumber", en: "Source URL" })}
                </dt>
                <dd className="mt-1 break-all text-xs text-foreground">
                  qq101uok.com/Contact
                </dd>
              </div>
            </dl>
            <Badge variant="outline">
              <CheckCircleIcon data-icon="inline-start" />{" "}
              {localize(language, {
                id: "Fixture terverifikasi",
                en: "Fixture verified",
              })}
            </Badge>
            <button
              className="mt-6 flex w-full items-center justify-between border-t border-border pt-4 text-sm font-semibold text-[var(--hk-pink)] hover:underline"
              type="button"
              onClick={() => setSelected(artifact)}
            >
              {localize(language, {
                id: "Periksa artefak",
                en: "Inspect artifact",
              })}{" "}
              <span>↗</span>
            </button>
          </article>
        ))}
      </div>
      <Dialog
        open={selected !== null}
        onOpenChange={(open) => !open && setSelected(null)}
      >
        <DialogContent className="max-h-[85vh] max-w-3xl overflow-auto border-border bg-popover text-popover-foreground shadow-2xl">
          <DialogHeader>
            <DialogTitle>
              {selected
                ? localize(language, selected.title)
                : localize(language, { id: "Artefak", en: "Artifact" })}
            </DialogTitle>
            <DialogDescription>
              {localize(language, {
                id: "Materi sumber yang dipreservasi dengan referensi integritas stabil.",
                en: "Preserved source material with a stable integrity reference.",
              })}
            </DialogDescription>
          </DialogHeader>
          {selected?.id === "screenshot" ? (
            <img
              className="w-full rounded-xl border border-border"
              src={screenshot}
              alt={localize(language, {
                id: "Pratinjau artefak screenshot HAWK-EYE terkendali",
                en: "Controlled HAWK-EYE screenshot artifact preview",
              })}
            />
          ) : (
            <pre className="overflow-auto rounded-xl bg-[#07131f] p-5 font-mono text-xs leading-7 text-teal-100">
              {selected?.id === "html"
                ? `<section id="contact">\n  <a href="https://t.me/…">Telegram</a>\n  <span>+63 915 780 0101</span>\n</section>`
                : `{\n  "type": "public_contact",\n  "value": "+639157800101",\n  "source": "/Contact",\n  "review": "unreviewed"\n}`}
            </pre>
          )}
          <dl className="mt-5 grid gap-3 sm:grid-cols-3">
            <div>
              <dt className="text-[0.65rem] font-semibold tracking-wide text-muted-foreground uppercase">
                {localize(language, { id: "Artefak", en: "Artifact" })}
              </dt>
              <dd className="mt-1 break-all text-xs">{selected?.file}</dd>
            </div>
            <div>
              <dt className="text-[0.65rem] font-semibold tracking-wide text-muted-foreground uppercase">
                {localize(language, { id: "Integritas", en: "Integrity" })}
              </dt>
              <dd className="mt-1 break-all font-mono text-xs">
                {selected?.hash}
              </dd>
            </div>
            <div>
              <dt className="text-[0.65rem] font-semibold tracking-wide text-muted-foreground uppercase">
                {localize(language, { id: "Lingkup", en: "Scope" })}
              </dt>
              <dd className="mt-1 text-xs">
                {localize(language, {
                  id: "Fixture demonstrasi terkendali",
                  en: "Controlled demonstration fixture",
                })}
              </dd>
            </div>
          </dl>
        </DialogContent>
      </Dialog>
    </>
  );
}
