export function valueOr(value: unknown, fallback = "Not recorded"): string {
  return value === undefined || value === null || value === ""
    ? fallback
    : String(value)
}

export function titleCase(value: unknown): string {
  return valueOr(value)
    .replaceAll("_", " ")
    .replaceAll(".", " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase())
}

export function truncate(value: unknown, length = 44): string {
  const text = valueOr(value, "Untitled")
  return text.length <= length ? text : `${text.slice(0, length - 1)}…`
}

export function formatTime(value?: string | null): string {
  if (!value) return "Time not recorded"
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return value
  return new Intl.DateTimeFormat("en-GB", {
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
    timeZone: "Asia/Jakarta",
  }).format(parsed)
}

export function exactTime(value?: string | null): string {
  if (!value) return "Time not recorded"
  const parsed = new Date(value)
  return Number.isNaN(parsed.getTime())
    ? value
    : `${parsed.toISOString()} · source ${value}`
}

export function hostnameFrom(value?: string | null): string {
  if (!value) return "saved evidence"
  try {
    return new URL(value).hostname.replace(/^www\./, "")
  } catch {
    return value.split("/")[0] || "saved evidence"
  }
}

export function formatElapsed(
  startedAt?: string | null,
  now = Date.now()
): string {
  if (!startedAt) return "00:00"
  const started = new Date(startedAt).getTime()
  const elapsedSeconds = Math.max(0, Math.floor((now - started) / 1000))
  const minutes = String(Math.floor(elapsedSeconds / 60)).padStart(2, "0")
  const seconds = String(elapsedSeconds % 60).padStart(2, "0")
  return `${minutes}:${seconds}`
}

export function pluralize(
  value: number,
  singular: string,
  plural = `${singular}s`
): string {
  return `${value} ${value === 1 ? singular : plural}`
}
