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

const artifacts = [
  {
    id: "screenshot",
    index: "01",
    title: "Screenshot evidence",
    file: "screenshot-contact-full.png",
    hash: "sha256: 7b8f…9a1c",
    icon: <FileImageIcon />,
    summary: "Full-page visual record of the public contact route.",
  },
  {
    id: "html",
    index: "02",
    title: "HTML snapshot",
    file: "rendered-contact.html",
    hash: "sha256: 2e40…d7af",
    icon: <CodeIcon />,
    summary: "Bounded rendered markup preserved before extraction.",
  },
  {
    id: "observation",
    index: "03",
    title: "Extracted observation",
    file: "observation-00042.json",
    hash: "sha256: a6d9…42bc",
    icon: <FingerprintIcon />,
    summary: "Normalized public identifier with explicit source references.",
  },
];

export function ArtifactGallery({ screenshot }: { screenshot: string }) {
  const [selected, setSelected] = useState<(typeof artifacts)[number] | null>(
    null,
  );
  return (
    <>
      <div className="artifact-grid">
        {artifacts.map((artifact) => (
          <article className="artifact-card" key={artifact.id}>
            <div className="artifact-card__top">
              <span>{artifact.index}</span>
              <i>{artifact.icon}</i>
            </div>
            <h3>{artifact.title}</h3>
            <p>{artifact.summary}</p>
            <dl>
              <div>
                <dt>File hash</dt>
                <dd>{artifact.hash}</dd>
              </div>
              <div>
                <dt>Timestamp</dt>
                <dd>12 Aug 2026 · 07:03:13 WIB</dd>
              </div>
              <div>
                <dt>Source URL</dt>
                <dd>qq101uok.com/Contact</dd>
              </div>
            </dl>
            <Badge variant="outline">
              <CheckCircleIcon data-icon="inline-start" /> Fixture verified
            </Badge>
            <button
              className="artifact-card__button"
              type="button"
              onClick={() => setSelected(artifact)}
            >
              Inspect artifact <span>↗</span>
            </button>
          </article>
        ))}
      </div>
      <Dialog
        open={selected !== null}
        onOpenChange={(open) => !open && setSelected(null)}
      >
        <DialogContent className="artifact-dialog max-w-3xl">
          <DialogHeader>
            <DialogTitle>{selected?.title ?? "Artifact"}</DialogTitle>
            <DialogDescription>
              Preserved source material with a stable integrity reference.
            </DialogDescription>
          </DialogHeader>
          {selected?.id === "screenshot" ? (
            <img
              className="artifact-preview"
              src={screenshot}
              alt="Controlled HAWK-EYE screenshot artifact preview"
            />
          ) : (
            <pre className="artifact-code">
              {selected?.id === "html"
                ? `<section id="contact">\n  <a href="https://t.me/…">Telegram</a>\n  <span>+63 915 780 0101</span>\n</section>`
                : `{\n  "type": "public_contact",\n  "value": "+639157800101",\n  "source": "/Contact",\n  "review": "unreviewed"\n}`}
            </pre>
          )}
          <dl className="artifact-dialog-meta">
            <div>
              <dt>Artifact</dt>
              <dd>{selected?.file}</dd>
            </div>
            <div>
              <dt>Integrity</dt>
              <dd>{selected?.hash}</dd>
            </div>
            <div>
              <dt>Scope</dt>
              <dd>Controlled demonstration fixture</dd>
            </div>
          </dl>
        </DialogContent>
      </Dialog>
    </>
  );
}
