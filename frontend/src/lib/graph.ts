import type {
  CaseDetails,
  CaseListItem,
  InvestigationEvent,
  ObservationRecord,
  RawGraphEdge,
  RawGraphNode,
  RunDetails,
} from "@/api/types"
import { formatTime, hostnameFrom, titleCase } from "@/lib/format"

export type VisualKind =
  | "page"
  | "contact"
  | "brand"
  | "transaction"
  | "offer"
  | "destination"
  | "candidate"
  | "other"

export type NodeShape = "circle" | "roundSquare" | "diamond" | "hex"

export interface NodePresentation {
  visualKind: VisualKind
  label: string
  color: string
  icon: string
  shape: NodeShape
}

export interface GraphNode {
  id: string
  kind: string
  label: string
  status: string
  attributes: Record<string, unknown>
  cluster: string
  sequence: number
  primary: boolean
  radius: number
  presentation: NodePresentation
}

export interface GraphEdge {
  id: string
  source: string
  target: string
  relation: string
  appearance: string
  sequence: number
  evidence: Record<string, unknown> | null
  seed: number
}

export interface TimelineItem {
  sequence: number
  label: string
  detail: string
  occurredAt?: string | null
  targetId?: string | null
  event?: InvestigationEvent
}

export interface GraphProjection {
  nodes: GraphNode[]
  edges: GraphEdge[]
  timeline: TimelineItem[]
  mode: string
}

export const GRAPH_FILTERS: Array<{
  key: VisualKind
  label: string
  color: string
  icon: string
}> = [
  { key: "page", label: "Pages", color: "#ef276f", icon: "▤" },
  { key: "contact", label: "Contacts", color: "#18c9b5", icon: "@" },
  { key: "brand", label: "Claimed brands", color: "#ff9d2e", icon: "◇" },
  { key: "transaction", label: "Transactions", color: "#ff9d2e", icon: "$" },
  { key: "offer", label: "Offers", color: "#f5cb5c", icon: "%" },
  { key: "destination", label: "Destinations", color: "#3abff0", icon: "↗" },
  { key: "candidate", label: "Candidates", color: "#9a73ff", icon: "☆" },
  { key: "other", label: "Other evidence", color: "#91a0b4", icon: "···" },
]

const CONTACT_TYPES = new Set([
  "public_telegram_alias",
  "public_telegram_contact",
  "public_whatsapp_link",
  "public_phone_number",
  "public_email_address",
])

const CLAIM_CATEGORIES = new Map([
  ["public_payment_method", "Payment indicators"],
  ["public_payment_provider", "Payment indicators"],
  ["public_offer_claim", "Offer claims"],
  ["public_legal_or_license_claim", "Legal claims"],
  ["public_referral_code", "Referral markers"],
  ["public_tracking_identifier", "Tracking markers"],
])

export function hash(value: unknown): number {
  let result = 2166136261
  for (const character of String(value)) {
    result ^= character.charCodeAt(0)
    result = Math.imul(result, 16777619)
  }
  return result >>> 0
}

export function seededUnit(value: unknown): number {
  return (hash(value) % 10_000) / 10_000
}

export function nodeKind(rawType?: string): string {
  const type = String(rawType || "default").toLowerCase()
  if (type.includes("screenshot")) return "screenshot"
  if (type.includes("readiness")) return "readiness"
  if (
    type.includes("html") ||
    type.includes("text") ||
    type.includes("network")
  ) {
    return "document"
  }
  if (type.includes("candidate")) return "candidate_domain"
  return type
}

export function presentationFor(
  item: Pick<GraphNode, "kind" | "attributes">
): NodePresentation {
  const kind = item.kind
  const observation = (item.attributes.observation ??
    {}) as Partial<ObservationRecord>
  const observationType = String(
    item.attributes.observation_type ?? observation.type ?? ""
  ).toLowerCase()
  const category = String(item.attributes.claim_category ?? "").toLowerCase()
  if (
    ["case", "domain", "page", "seed_page", "collected_page"].includes(kind)
  ) {
    return {
      visualKind: "page",
      label: "Page",
      color: "#ef276f",
      icon: "▤",
      shape: "roundSquare",
    }
  }
  if (kind === "public_contact") {
    if (observationType.includes("whatsapp")) {
      return {
        visualKind: "contact",
        label: "WhatsApp",
        color: "#18c9b5",
        icon: "WA",
        shape: "circle",
      }
    }
    if (observationType.includes("telegram")) {
      return {
        visualKind: "contact",
        label: "Telegram",
        color: "#18c9b5",
        icon: "TG",
        shape: "circle",
      }
    }
    if (observationType.includes("email")) {
      return {
        visualKind: "contact",
        label: "Email",
        color: "#18c9b5",
        icon: "@",
        shape: "circle",
      }
    }
    if (observationType.includes("phone")) {
      return {
        visualKind: "contact",
        label: "Phone",
        color: "#18c9b5",
        icon: "TEL",
        shape: "circle",
      }
    }
    return {
      visualKind: "contact",
      label: "Contact",
      color: "#18c9b5",
      icon: "ID",
      shape: "circle",
    }
  }
  if (kind === "claimed_brand") {
    return {
      visualKind: "brand",
      label: "Claimed brand",
      color: "#ff9d2e",
      icon: "◇",
      shape: "hex",
    }
  }
  if (
    kind === "public_claim" &&
    (category.includes("payment") || category.includes("transaction"))
  ) {
    return {
      visualKind: "transaction",
      label: "Transaction",
      color: "#ff9d2e",
      icon: "$",
      shape: "hex",
    }
  }
  if (kind === "public_claim" && category.includes("offer")) {
    return {
      visualKind: "offer",
      label: "Offer",
      color: "#f5cb5c",
      icon: "%",
      shape: "hex",
    }
  }
  if (["external_destination", "redirect_target"].includes(kind)) {
    return {
      visualKind: "destination",
      label: kind === "redirect_target" ? "Redirect" : "Destination",
      color: "#3abff0",
      icon: kind === "redirect_target" ? "↪" : "↗",
      shape: "diamond",
    }
  }
  if (["candidate", "candidate_domain"].includes(kind)) {
    return {
      visualKind: "candidate",
      label: "Candidate",
      color: "#9a73ff",
      icon: "☆",
      shape: "diamond",
    }
  }
  return {
    visualKind: "other",
    label: "Other evidence",
    color: "#91a0b4",
    icon: "···",
    shape: "circle",
  }
}

function clusterFor(kind: string): string {
  if (
    ["case", "domain", "page", "seed_page", "collected_page"].includes(kind)
  ) {
    return "Captured pages"
  }
  if (["screenshot", "document", "readiness"].includes(kind))
    return "Evidence artifacts"
  if (
    ["observation", "public_contact", "public_claim", "claimed_brand"].includes(
      kind
    )
  ) {
    return "Public observations"
  }
  if (
    [
      "candidate",
      "candidate_domain",
      "external_destination",
      "redirect_target",
    ].includes(kind)
  ) {
    return "Linked destinations"
  }
  return "Evidence graph"
}

function normalizeNode(
  raw: RawGraphNode,
  index: number,
  extras: {
    primary?: boolean
    sequence?: number
    cluster?: string
    attributes?: Record<string, unknown>
    status?: string
  } = {}
): GraphNode {
  const kind = nodeKind(raw.kind)
  const core = {
    id: String(raw.id),
    kind,
    label: String(raw.label ?? raw.id),
    status: raw.status ?? extras.status ?? "observed",
    attributes: raw.attributes ?? extras.attributes ?? {},
    cluster: extras.cluster ?? clusterFor(kind),
    sequence: Number(extras.sequence ?? index + 1),
    primary: Boolean(extras.primary),
    radius: extras.primary
      ? 20
      : ["case", "domain", "page", "seed_page", "collected_page"].includes(kind)
        ? 15
        : 12,
  }
  return { ...core, presentation: presentationFor(core) }
}

function normalizeEdge(
  raw: RawGraphEdge,
  index: number,
  extras: { sequence?: number; appearance?: string } = {}
): GraphEdge {
  const source = typeof raw.source === "object" ? raw.source.id : raw.source
  const target = typeof raw.target === "object" ? raw.target.id : raw.target
  return {
    id: String(raw.id || `edge-${index}`),
    source: String(source),
    target: String(target),
    relation: String(raw.relation ?? raw.type ?? "recorded relation"),
    appearance: raw.appearance ?? extras.appearance ?? "solid",
    sequence: Number(extras.sequence ?? index + 2),
    evidence: raw.evidence ?? null,
    seed: seededUnit(raw.id || `${source}-${target}`),
  }
}

function addNode(nodes: GraphNode[], node: GraphNode): void {
  if (!nodes.some((item) => item.id === node.id)) nodes.push(node)
}

function addEdge(edges: GraphEdge[], edge: GraphEdge): void {
  if (!edges.some((item) => item.id === edge.id)) edges.push(edge)
}

export function buildCaseProjection(
  details: CaseDetails,
  knownCases: CaseListItem[] = []
): GraphProjection {
  const nodes: GraphNode[] = []
  const edges: GraphEdge[] = []
  const timeline: TimelineItem[] = []
  const pages = details.pages ?? []
  const primaryPage = pages[0]
  const pageIds = new Map<string, string>()

  pages.forEach((page, index) => {
    const nodeId = `page:${page.id}`
    pageIds.set(page.id, nodeId)
    addNode(
      nodes,
      normalizeNode(
        {
          id: nodeId,
          kind: index === 0 ? "seed_page" : "collected_page",
          label: page.final_url_display ?? page.id,
          status: "collected",
          attributes: { page, source_case_id: details.case_id },
        },
        index,
        { primary: index === 0, sequence: index + 1, cluster: "Captured pages" }
      )
    )
    if (index > 0 && primaryPage) {
      addEdge(
        edges,
        normalizeEdge(
          {
            id: `crawl:${primaryPage.id}:${page.id}`,
            source: `page:${primaryPage.id}`,
            target: nodeId,
            relation: "crawled same-site page",
          },
          edges.length,
          { sequence: index + 1 }
        )
      )
    }
  })

  if (!nodes.length) {
    addNode(
      nodes,
      normalizeNode(
        {
          id: `page:${details.case_id}`,
          kind: "seed_page",
          label:
            details.final_url_display ??
            details.seed_url_display ??
            details.case_id,
          status: "collected",
        },
        0,
        { primary: true, sequence: 1 }
      )
    )
  }

  const rootId = (primaryPage && pageIds.get(primaryPage.id)) || nodes[0].id
  let sequence = Math.max(2, pages.length + 1)
  timeline.push({
    sequence: 1,
    label: "Capture started",
    detail: formatTime(details.started_at),
    occurredAt: details.started_at,
    targetId: rootId,
  })
  pages.forEach((page, index) => {
    timeline.push({
      sequence: index + 2,
      label: index === 0 ? "Seed page captured" : "Same-site page captured",
      detail: `${titleCase(page.capture_adequacy)} · ${hostnameFrom(page.final_url_display)}`,
      targetId: pageIds.get(page.id),
    })
  })

  const knownByHost = new Map(
    knownCases
      .filter((item) => item.integrity === "verified")
      .map((item) => [hostnameFrom(item.final_url_display), item])
  )
  const sourceHost = hostnameFrom(
    details.final_url_display ?? details.seed_url_display
  )
  const token =
    sourceHost.match(/[a-z]+\d+|\d+[a-z]+|\d{3,}/i)?.[0]?.toLowerCase() ?? ""
  const candidateHosts = new Set(
    (details.candidates ?? []).map((item) => item.hostname)
  )
  const destinations = new Map<
    string,
    {
      host: string
      url: string
      sourcePageId?: string
      sources: unknown[]
      redirect: boolean
      known?: CaseListItem
    }
  >()
  const addDestination = (
    url: string,
    sourcePageId: string | undefined,
    source: unknown,
    redirect = false
  ) => {
    const host = hostnameFrom(url)
    if (!host || host === sourceHost) return
    const known = knownByHost.get(host)
    const related = Boolean(
      known || candidateHosts.has(host) || (token && host.includes(token))
    )
    if (!related) return
    const existing = destinations.get(host) ?? {
      host,
      url,
      sourcePageId,
      sources: [],
      redirect,
      known,
    }
    existing.sources.push(source)
    existing.known ??= known
    existing.redirect ||= redirect
    destinations.set(host, existing)
  }
  for (const item of details.frontier ?? []) {
    if (item.normalized_url_display) {
      addDestination(
        item.normalized_url_display,
        item.source_page_id,
        item,
        item.discovery_method === "redirect"
      )
    }
  }
  for (const observation of details.observations ?? []) {
    if (
      ["public_outgoing_link", "public_redirect_target"].includes(
        observation.type
      )
    ) {
      addDestination(
        observation.display_value,
        observation.source_page_id,
        observation,
        observation.type === "public_redirect_target"
      )
    }
  }

  for (const destination of destinations.values()) {
    sequence += 1
    const nodeId = `destination:${destination.host}`
    const status = destination.known ? "collected" : "lead"
    addNode(
      nodes,
      normalizeNode(
        {
          id: nodeId,
          kind: destination.redirect
            ? "redirect_target"
            : destination.known
              ? "external_destination"
              : "candidate_domain",
          label: destination.host,
          status,
          attributes: {
            url: destination.url,
            observations: destination.sources,
            matched_case_id: destination.known?.case_id,
            relationship: destination.known
              ? "observed link to saved capture"
              : "Relationship: not determined",
          },
        },
        nodes.length,
        { sequence, status, cluster: "Linked destinations" }
      )
    )
    const sourceId =
      (destination.sourcePageId && pageIds.get(destination.sourcePageId)) ||
      rootId
    addEdge(
      edges,
      normalizeEdge(
        {
          id: `destination-edge:${sourceId}:${nodeId}`,
          source: sourceId,
          target: nodeId,
          relation: destination.redirect
            ? "publicly redirects to"
            : "publicly links to",
        },
        edges.length,
        {
          sequence,
          appearance: status === "lead" ? "dashed" : "solid_emphasized",
        }
      )
    )
    timeline.push({
      sequence,
      label: destination.known
        ? "Saved destination matched"
        : "Candidate lead observed",
      detail: destination.host,
      targetId: nodeId,
    })
  }

  const directSignals = (details.observations ?? [])
    .filter(
      (item) =>
        item.type === "claimed_brand_identity" || CONTACT_TYPES.has(item.type)
    )
    .slice(0, 18)
  for (const observation of directSignals) {
    sequence += 1
    const kind =
      observation.type === "claimed_brand_identity"
        ? "claimed_brand"
        : "public_contact"
    const nodeId = `observation:${observation.id}`
    addNode(
      nodes,
      normalizeNode(
        {
          id: nodeId,
          kind,
          label: observation.display_value,
          status: "observed",
          attributes: { observation },
        },
        nodes.length,
        { sequence, cluster: "Public observations" }
      )
    )
    const sourceId =
      (observation.source_page_id && pageIds.get(observation.source_page_id)) ||
      rootId
    addEdge(
      edges,
      normalizeEdge(
        {
          id: `observed:${sourceId}:${nodeId}`,
          source: sourceId,
          target: nodeId,
          relation:
            observation.type === "claimed_brand_identity"
              ? "claims brand"
              : "publishes public contact",
        },
        edges.length,
        { sequence }
      )
    )
    timeline.push({
      sequence,
      label: titleCase(observation.type),
      detail: "Evidence-backed semantic observation",
      targetId: nodeId,
    })
  }

  const claimGroups = new Map<
    string,
    {
      sourceId: string
      category: string
      values: string[]
      observations: ObservationRecord[]
    }
  >()
  for (const observation of details.observations ?? []) {
    const category = CLAIM_CATEGORIES.get(observation.type)
    if (!category) continue
    const sourceId =
      (observation.source_page_id && pageIds.get(observation.source_page_id)) ||
      rootId
    const key = `${sourceId}:${category}`
    const group = claimGroups.get(key) ?? {
      sourceId,
      category,
      values: [],
      observations: [],
    }
    if (!group.values.includes(observation.display_value))
      group.values.push(observation.display_value)
    group.observations.push(observation)
    claimGroups.set(key, group)
  }
  for (const group of claimGroups.values()) {
    sequence += 1
    const nodeId = `claim:${group.sourceId}:${group.category.toLowerCase().replaceAll(" ", "-")}`
    addNode(
      nodes,
      normalizeNode(
        {
          id: nodeId,
          kind: "public_claim",
          label: `${group.category} · ${group.values.slice(0, 4).join(", ")}`,
          status: "observed",
          attributes: {
            claim_category: group.category,
            values: group.values,
            observations: group.observations,
          },
        },
        nodes.length,
        { sequence, cluster: "Public observations" }
      )
    )
    addEdge(
      edges,
      normalizeEdge(
        {
          id: `claim-edge:${group.sourceId}:${nodeId}`,
          source: group.sourceId,
          target: nodeId,
          relation: "displays public claim",
        },
        edges.length,
        { sequence }
      )
    )
    timeline.push({
      sequence,
      label: group.category,
      detail: `${group.values.length} evidence-backed public claim${group.values.length === 1 ? "" : "s"}`,
      targetId: nodeId,
    })
  }

  for (const record of details.evidence ?? []) {
    if (!record.type.includes("screenshot")) continue
    sequence += 1
    timeline.push({
      sequence,
      label: titleCase(record.type),
      detail: `${formatTime(record.collected_at)} · saved image evidence`,
      occurredAt: record.collected_at,
      targetId: (record.page_id && pageIds.get(record.page_id)) || rootId,
    })
  }
  timeline.push({
    sequence: sequence + 1,
    label:
      details.capture_adequacy === "adequate"
        ? "Capture adequate"
        : "Capture limited",
    detail: `${titleCase(details.extraction_tier || "none")} evidence · ${formatTime(details.completed_at)}`,
    occurredAt: details.completed_at,
    targetId: rootId,
  })
  return { nodes, edges, timeline, mode: "Public evidence relations" }
}

function eventLabel(event: InvestigationEvent): string | null {
  const labels: Record<string, string> = {
    "run.started": "Investigation started",
    "collection.started": "Bounded crawl started",
    "artifact.captured": event.payload?.interaction_artifact
      ? "Interaction evidence saved"
      : "Page evidence saved",
    "agent.objective.created": "Agent objective issued",
    "agent.fallback.activated": "Safe fallback activated",
    "tool.requested": "Agent action selected",
    "tool.completed": "Safe action completed",
    "search.lead.discovered": "Candidate lead observed",
    "candidate_page.approval_required": "Collection approval required",
    "candidate_page.approved": "Candidate collection approved",
    "candidate_page.collected": "Candidate page collected",
    "assertion.proposed": "Review assertion proposed",
    "review.required": "Human review required",
    "run.completed": "Investigation completed",
  }
  return labels[event.kind] ?? null
}

export function buildRunProjection(details: RunDetails): GraphProjection {
  const eventSequence = new Map(
    (details.events ?? []).map((event) => [event.event_id, event.sequence])
  )
  const animationSequence = new Map<string, number>()
  for (const animation of details.graph?.animations ?? []) {
    animationSequence.set(
      animation.target_id,
      Math.min(
        animationSequence.get(animation.target_id) ?? Number.POSITIVE_INFINITY,
        animation.sequence
      )
    )
  }
  const nodes = (details.graph?.nodes ?? []).map((raw, index) =>
    normalizeNode(raw, index, {
      primary: raw.kind === "seed_page",
      sequence: animationSequence.get(raw.id) ?? index + 1,
      cluster: [
        "external_destination",
        "redirect_target",
        "candidate_domain",
      ].includes(raw.kind)
        ? "Linked destinations"
        : undefined,
    })
  )
  const edges = (details.graph?.edges ?? []).map((raw, index) => {
    const supporting = raw.supporting_event_ids ?? []
    const supportedSequences = supporting
      .map((id) => eventSequence.get(id))
      .filter((value): value is number => value !== undefined)
    return normalizeEdge(raw, index, {
      sequence: supportedSequences.length
        ? Math.min(...supportedSequences)
        : index + 2,
    })
  })

  const observations = (details.events ?? []).filter(
    (event) => event.kind === "observation.created"
  )
  const blocked = (details.events ?? []).filter(
    (event) => event.kind === "tool.blocked" && event.payload?.policy_preflight
  )
  const timeline: TimelineItem[] = []
  let observationsAdded = false
  let blockedAdded = false

  for (const event of details.events ?? []) {
    if (
      event.kind === "interactive_element.discovered" ||
      event.kind === "entity.matched"
    )
      continue
    if (
      event.kind === "tool.requested" &&
      (event.payload?.executed === false ||
        event.payload?.action === "policy_preflight")
    ) {
      continue
    }
    const targetId = (details.graph?.animations ?? []).find(
      (item) => item.sequence === event.sequence
    )?.target_id
    if (event.kind === "tool.blocked" && event.payload?.policy_preflight) {
      if (blockedAdded) continue
      blockedAdded = true
      timeline.push({
        sequence: event.sequence,
        label: `${blocked.length} unsafe controls blocked`,
        detail: "Policy preflight only · never executed",
        occurredAt: event.occurred_at,
        targetId,
        event,
      })
      continue
    }
    if (event.kind === "observation.created") {
      if (observationsAdded) continue
      observationsAdded = true
      timeline.push({
        sequence: event.sequence,
        label: "Semantic evidence extracted",
        detail: `${observations.length} evidence-backed observations`,
        occurredAt: event.occurred_at,
        targetId,
        event,
      })
      continue
    }
    const label = eventLabel(event)
    if (!label) continue
    const detail = String(
      event.payload?.url ??
        event.payload?.label ??
        formatTime(event.occurred_at)
    )
    timeline.push({
      sequence: event.sequence,
      label,
      detail,
      occurredAt: event.occurred_at,
      targetId,
      event,
    })
  }
  return { nodes, edges, timeline, mode: "Live investigation replay" }
}

export function timelinePresentation(item: TimelineItem): {
  icon: string
  color: string
} {
  const kind = String(item.event?.kind || item.label).toLowerCase()
  if (kind.includes("blocked") || kind.includes("failed"))
    return { icon: "!", color: "#ff6577" }
  if (kind.includes("review") || kind.includes("assertion"))
    return { icon: "✓", color: "#34d399" }
  if (kind.includes("candidate") || kind.includes("lead"))
    return { icon: "☆", color: "#9a73ff" }
  if (
    kind.includes("agent") ||
    kind.includes("tool") ||
    kind.includes("objective")
  )
    return { icon: "◇", color: "#3abff0" }
  if (
    kind.includes("observation") ||
    kind.includes("semantic") ||
    kind.includes("extract")
  )
    return { icon: "◉", color: "#18c9b5" }
  if (
    kind.includes("capture") ||
    kind.includes("page") ||
    kind.includes("artifact") ||
    kind.includes("crawl")
  )
    return { icon: "▤", color: "#ef276f" }
  if (kind.includes("completed") || kind.includes("adequate"))
    return { icon: "✓", color: "#34d399" }
  return { icon: "·", color: "#91a0b4" }
}
