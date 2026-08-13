import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { EvidenceGraph, type GraphBackground } from "@hawkeye/graph";
import {
  ArrowCounterClockwiseIcon,
  DownloadSimpleIcon,
  ExportIcon,
  PauseIcon,
  PlayIcon,
} from "@phosphor-icons/react";
import { Button, Card } from "@hawkeye/ui";

type Ratio = "16:9" | "9:16" | "1:1" | "4:5";
type Preset = "agent" | "replay" | "graph";
type Language = "id" | "en";

const ratios: Record<Ratio, { width: number; height: number; label: string }> =
  {
    "16:9": { width: 1920, height: 1080, label: "1920 × 1080" },
    "9:16": { width: 1080, height: 1920, label: "1080 × 1920" },
    "1:1": { width: 1080, height: 1080, label: "1080 × 1080" },
    "4:5": { width: 1080, height: 1350, label: "1080 × 1350" },
  };

function validRatio(value: string | null): Ratio {
  return value && value in ratios ? (value as Ratio) : "16:9";
}

function validBackground(value: string | null): GraphBackground {
  return value === "transparent" || value === "chroma" ? value : "dark";
}

function validPreset(value: string | null): Preset {
  return value === "replay" || value === "graph" ? value : "agent";
}

function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export function VideoGraphStudio({
  renderOnly = false,
}: {
  renderOnly?: boolean;
}) {
  const [ratio, setRatio] = useState<Ratio>("16:9");
  const [preset, setPreset] = useState<Preset>("agent");
  const [language, setLanguage] = useState<Language>("id");
  const [background, setBackground] = useState<GraphBackground>("dark");
  const [duration, setDuration] = useState(12);
  const [loop, setLoop] = useState(true);
  const [playing, setPlaying] = useState(true);
  const [elapsed, setElapsed] = useState(0);
  const [recording, setRecording] = useState(false);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const startRef = useRef(performance.now());

  useEffect(() => {
    const query = new URLSearchParams(window.location.search);
    setRatio(validRatio(query.get("ratio")));
    setPreset(validPreset(query.get("preset")));
    setBackground(validBackground(query.get("background")));
    const requestedDurationRaw = query.get("duration");
    const requestedDuration = Number(requestedDurationRaw);
    if (requestedDurationRaw !== null && Number.isFinite(requestedDuration))
      setDuration(Math.max(4, Math.min(30, requestedDuration)));
    setLoop(query.get("loop") !== "false");
    const requestedLanguage = query.get("language") === "en" ? "en" : "id";
    setLanguage(requestedLanguage);
    document.documentElement.dataset.language = requestedLanguage;
  }, []);

  useEffect(() => {
    document.documentElement.dataset.language = language;
    document.documentElement.lang = language;
  }, [language]);

  const restart = useCallback(() => {
    startRef.current = performance.now();
    setElapsed(0);
    setPlaying(true);
  }, []);

  useEffect(() => {
    if (!playing) return;
    let frame = 0;
    const tick = (time: number) => {
      const next = (time - startRef.current) / 1000;
      if (next >= duration) {
        if (loop) {
          startRef.current = time;
          setElapsed(0);
        } else {
          setElapsed(duration);
          setPlaying(false);
          return;
        }
      } else {
        setElapsed(next);
      }
      frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [duration, loop, playing]);

  const step =
    preset === "graph"
      ? 4
      : elapsed < duration * 0.18
        ? 0
        : elapsed < duration * 0.38
          ? 1
          : elapsed < duration * 0.66
            ? 2
            : 4;
  const output = ratios[ratio];
  const isEnglish = language === "en";
  const renderUrl = useMemo(() => {
    const query = new URLSearchParams({
      ratio,
      preset,
      background,
      duration: String(duration),
      loop: String(loop),
      language,
    });
    return `/video/graph/render?${query.toString()}`;
  }, [background, duration, language, loop, preset, ratio]);

  const saveFrame = () => {
    canvasRef.current?.toBlob((blob) => {
      if (blob)
        downloadBlob(blob, `hawkeye-graph-${ratio.replace(":", "x")}.png`);
    }, "image/png");
  };

  const recordVideo = async () => {
    const canvas = canvasRef.current;
    if (!canvas || recording || !("MediaRecorder" in window)) return;
    const mimeType = [
      "video/webm;codecs=vp9",
      "video/webm;codecs=vp8",
      "video/webm",
    ].find((type) => MediaRecorder.isTypeSupported(type));
    if (!mimeType) return;
    restart();
    const stream = canvas.captureStream(60);
    const recorder = new MediaRecorder(stream, {
      mimeType,
      videoBitsPerSecond: 16_000_000,
    });
    const chunks: BlobPart[] = [];
    recorder.ondataavailable = (event) =>
      event.data.size && chunks.push(event.data);
    recorder.onstop = () => {
      stream.getTracks().forEach((track) => track.stop());
      downloadBlob(
        new Blob(chunks, { type: mimeType }),
        `hawkeye-graph-${ratio.replace(":", "x")}.webm`,
      );
      setRecording(false);
    };
    setRecording(true);
    recorder.start(250);
    window.setTimeout(
      () => recorder.state !== "inactive" && recorder.stop(),
      duration * 1000,
    );
  };

  const graph = (
    <div
      className="video-graph-frame"
      data-background={background}
      style={
        renderOnly
          ? {
              aspectRatio: `${output.width} / ${output.height}`,
              width: `min(100vw, calc(100vh * ${output.width / output.height}))`,
              height: `min(100vh, calc(100vw * ${output.height / output.width}))`,
            }
          : {
              aspectRatio: `${output.width} / ${output.height}`,
              width: `min(100%, calc((100vh - 11rem) * ${output.width / output.height}))`,
            }
      }
    >
      <EvidenceGraph
        compact
        visibleStep={step}
        background={background}
        showAgent={preset === "agent"}
        showControls={!renderOnly}
        showMinimap={!renderOnly}
        showLegend={!renderOnly}
        showStatus={!renderOnly}
        showFallback={!renderOnly}
        outputWidth={output.width}
        outputHeight={output.height}
        onCanvasReady={(canvas) => {
          canvasRef.current = canvas;
        }}
      />
    </div>
  );

  if (renderOnly)
    return (
      <main className="video-render-surface" data-background={background}>
        {graph}
      </main>
    );

  return (
    <main className="video-studio-shell">
      <header className="video-studio-header">
        <div>
          <a href="/" className="video-studio-back">
            ← HAWK-EYE
          </a>
          <h1>
            {isEnglish ? "Graph capture studio" : "Studio perekaman graph"}
          </h1>
          <p>
            {isEnglish
              ? "Prepare clean graph footage without the site header, browser chrome, or marketing panels."
              : "Siapkan footage graph tanpa header situs, browser chrome, atau panel marketing."}
          </p>
        </div>
        <Button
          render={<a href={renderUrl} target="_blank" rel="noreferrer" />}
        >
          <ExportIcon data-icon="inline-start" />{" "}
          {isEnglish ? "Open clean render" : "Buka render bersih"}
        </Button>
      </header>

      <div className="video-studio-grid">
        <Card className="video-studio-controls">
          <label>
            {isEnglish ? "Ratio" : "Rasio"}
            <select
              value={ratio}
              onChange={(event) => setRatio(event.target.value as Ratio)}
            >
              {Object.entries(ratios).map(([value, item]) => (
                <option value={value} key={value}>
                  {value} · {item.label}
                </option>
              ))}
            </select>
          </label>
          <label>
            Preset
            <select
              value={preset}
              onChange={(event) => setPreset(event.target.value as Preset)}
            >
              <option value="agent">
                {isEnglish ? "Agentic exploration" : "Penelusuran agentic"}
              </option>
              <option value="replay">
                {isEnglish ? "Graph replay" : "Replay graph"}
              </option>
              <option value="graph">
                {isEnglish ? "Full graph" : "Graph lengkap"}
              </option>
            </select>
          </label>
          <label>
            {isEnglish ? "Background" : "Latar"}
            <select
              value={background}
              onChange={(event) =>
                setBackground(event.target.value as GraphBackground)
              }
            >
              <option value="dark">
                HAWK-EYE {isEnglish ? "dark" : "gelap"}
              </option>
              <option value="transparent">
                {isEnglish ? "Transparent" : "Transparan"} PNG / WebM*
              </option>
              <option value="chroma">
                {isEnglish ? "Chroma green" : "Chroma hijau"}
              </option>
            </select>
          </label>
          <label>
            {isEnglish ? "Language" : "Bahasa"}
            <select
              value={language}
              onChange={(event) => setLanguage(event.target.value as Language)}
            >
              <option value="id">Indonesia</option>
              <option value="en">English</option>
            </select>
          </label>
          <label>
            {isEnglish ? "Duration" : "Durasi"}
            <select
              value={duration}
              onChange={(event) => setDuration(Number(event.target.value))}
            >
              {[8, 12, 16, 20].map((value) => (
                <option value={value} key={value}>
                  {value} {isEnglish ? "seconds" : "detik"}
                </option>
              ))}
            </select>
          </label>
          <label className="video-studio-check">
            <input
              type="checkbox"
              checked={loop}
              onChange={(event) => setLoop(event.target.checked)}
            />{" "}
            {isEnglish ? "Loop preview" : "Ulangi preview"}
          </label>
          <div className="video-studio-actions">
            <Button variant="outline" onClick={restart}>
              <ArrowCounterClockwiseIcon /> {isEnglish ? "Restart" : "Ulangi"}
            </Button>
            <Button
              variant="outline"
              onClick={() => setPlaying((value) => !value)}
            >
              {playing ? <PauseIcon /> : <PlayIcon />}{" "}
              {playing
                ? isEnglish
                  ? "Pause"
                  : "Jeda"
                : isEnglish
                  ? "Play"
                  : "Putar"}
            </Button>
            <Button variant="outline" onClick={saveFrame}>
              <DownloadSimpleIcon /> PNG
            </Button>
            <Button onClick={recordVideo} disabled={recording}>
              <DownloadSimpleIcon />{" "}
              {recording ? (isEnglish ? "Recording…" : "Merekam…") : "WebM"}
            </Button>
          </div>
          <p className="video-studio-note">
            {isEnglish
              ? "Green screen can conflict with the WhatsApp icon. Use transparent for compositing or dark for ready-to-use footage. WebM alpha depends on codec and editor support; PNG preserves transparency."
              : "Green screen dapat berbenturan dengan ikon WhatsApp. Gunakan transparan untuk compositing, atau gelap untuk footage siap pakai. Alpha WebM bergantung pada dukungan codec dan editor; PNG tetap mempertahankan transparansi."}
          </p>
        </Card>

        <section className="video-studio-preview">
          {graph}
          <div className="video-studio-timeline">
            <span>{elapsed.toFixed(1)}s</span>
            <progress max={duration} value={elapsed} />
            <span>{duration}s</span>
          </div>
        </section>
      </div>
    </main>
  );
}
