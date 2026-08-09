import {
  ArrowSquareOut,
  Article,
  Browser,
  Check,
  ClipboardText,
  Code,
  EnvelopeSimple,
  File,
  FileHtml,
  Fingerprint,
  Globe,
  Image,
  Link,
  MagnifyingGlass,
  Phone,
  SealCheck,
  ShieldWarning,
  Star,
  Tag,
  TelegramLogo,
  WhatsappLogo,
} from "@phosphor-icons/react"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import { useDeferredValue, useMemo, useState } from "react"
import { toast } from "sonner"

import { api, caseArtifactUrl, runArtifactUrl } from "@/api/client"
import type {
  AssertionRecord,
  CaseDetails,
  EvidenceRecord,
  EvidenceSource,
  InvestigationEvent,
  ObservationRecord,
  ReviewRecord,
  RunDetails,
} from "@/api/types"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { ScrollArea } from "@/components/ui/scroll-area"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Textarea } from "@/components/ui/textarea"
import {
  exactTime,
  formatTime,
  hostnameFrom,
  titleCase,
  valueOr,
} from "@/lib/format"
import type { GraphNode, GraphProjection } from "@/lib/graph"
import { cn } from "@/lib/utils"

interface EvidenceCardModel {
  id: string
  title: string
  value: string
  kind:
    | "artifact"
    | "contact"
    | "brand"
    | "transaction"
    | "offer"
    | "destination"
    | "candidate"
    | "assertion"
    | "review"
    | "other"
  occurredAt?: string | null
  nodeId?: string | null
  previewUrl?: string | null
  facts: Array<[string, unknown]>
}

interface ScreenshotChoice {
  label: string
  record: EvidenceRecord
}

function sourceCase(source: EvidenceSource): CaseDetails | undefined {
  return source.kind === "case"
    ? source.details
    : (source.details.source_case ?? undefined)
}

function observationKind(
  observation: ObservationRecord
): EvidenceCardModel["kind"] {
  const type = observation.type.toLowerCase()
  if (
    type.includes("whatsapp") ||
    type.includes("telegram") ||
    type.includes("phone") ||
    type.includes("email")
  )
    return "contact"
  if (type === "claimed_brand_identity") return "brand"
  if (type.includes("payment")) return "transaction"
  if (type.includes("offer")) return "offer"
  if (
    type.includes("outgoing") ||
    type.includes("redirect") ||
    type.includes("download")
  )
    return "destination"
  return "other"
}

function CardIcon({ card }: { card: EvidenceCardModel }) {
  let Icon = Article
  if (card.kind === "contact") {
    const title = card.title.toLowerCase()
    if (title.includes("whatsapp")) Icon = WhatsappLogo
    else if (title.includes("telegram")) Icon = TelegramLogo
    else if (title.includes("email")) Icon = EnvelopeSimple
    else Icon = Phone
  } else if (card.kind === "brand") Icon = Tag
  else if (card.kind === "transaction") Icon = Fingerprint
  else if (card.kind === "offer") Icon = SealCheck
  else if (card.kind === "destination") Icon = Link
  else if (card.kind === "candidate") Icon = Star
  else if (card.kind === "assertion") Icon = ClipboardText
  else if (card.kind === "review") Icon = Check
  else if (card.previewUrl) Icon = Image
  else if (card.title.toLowerCase().includes("html")) Icon = FileHtml
  else if (card.kind === "artifact") Icon = File
  return <Icon weight="duotone" />
}

function findNodeForObservation(
  projection: GraphProjection,
  observation: ObservationRecord
): string | null {
  const direct = projection.nodes.find((node) => {
    const attached = node.attributes.observation as
      ObservationRecord | undefined
    const observations = node.attributes.observations as
      ObservationRecord[] | undefined
    return (
      attached?.id === observation.id ||
      observations?.some((item) => item.id === observation.id)
    )
  })
  if (direct) return direct.id
  return (
    projection.nodes.find(
      (node) => node.id === `page:${observation.source_page_id}`
    )?.id ?? null
  )
}

function caseEvidenceCards(
  details: CaseDetails,
  projection: GraphProjection
): EvidenceCardModel[] {
  const cards: EvidenceCardModel[] = []
  const indicatorMap = new Map(
    (details.gambling_indicators?.classifications ?? []).map((item) => [
      item.observation_id,
      item,
    ])
  )
  for (const record of details.evidence ?? []) {
    const pageNode = projection.nodes.find(
      (node) => node.id === `page:${record.page_id}`
    )
    const isImage = record.type.toLowerCase().includes("screenshot")
    cards.push({
      id: `artifact:${record.id}`,
      title: titleCase(record.type),
      value: record.id,
      kind: "artifact",
      occurredAt: record.collected_at,
      nodeId: pageNode?.id,
      previewUrl: isImage ? caseArtifactUrl(details.case_id, record.id) : null,
      facts: [
        ["Artifact ID", record.id],
        ["Source page", record.page_id],
        ["Collected", exactTime(record.collected_at)],
        ["SHA-256", record.sha256],
        [
          "Dimensions",
          record.image_dimensions
            ? `${record.image_dimensions.width} × ${record.image_dimensions.height}`
            : null,
        ],
        [
          "Integrity",
          record.artifact_available ? "Verified and available" : "Unavailable",
        ],
      ],
    })
  }
  for (const observation of details.observations ?? []) {
    const indicator = indicatorMap.get(observation.id)
    const kind = observationKind(observation)
    const screenshotId =
      observation.crop_evidence_id || observation.screenshot_evidence_id
    cards.push({
      id: `observation:${observation.id}`,
      title: observationTitle(observation),
      value: observation.display_value,
      kind,
      nodeId: findNodeForObservation(projection, observation),
      previewUrl: screenshotId
        ? caseArtifactUrl(details.case_id, screenshotId)
        : null,
      facts: [
        ["Observation ID", observation.id],
        ["Type", titleCase(observation.type)],
        ["Source page", observation.source_page_id],
        ["Source artifact", observation.source_artifact_id],
        ["Screenshot", observation.screenshot_evidence_id],
        ["Extraction", observation.extraction_method],
        ["Context", observation.surrounding_text],
        ["Evidence status", observation.evidence_strength],
        [
          "Judol policy",
          indicator?.label === "indicator"
            ? `Counted · ${titleCase(indicator.category)}`
            : "Not counted",
        ],
        ["Limitations", observation.limitations?.join(" · ")],
      ],
    })
  }
  for (const candidate of details.candidates ?? []) {
    const node = projection.nodes.find(
      (item) => item.label === candidate.hostname
    )
    cards.push({
      id: `candidate:${candidate.candidate_id || candidate.id || candidate.hostname}`,
      title: "Pending candidate lead",
      value: candidate.hostname,
      kind: "candidate",
      nodeId: node?.id,
      facts: [
        ["Relationship", "Not determined"],
        ["State", candidate.state || "pending"],
        ["Meaning", "Lead only · no ownership or operator attribution"],
      ],
    })
  }
  return cards
}

function observationTitle(observation: ObservationRecord): string {
  const type = observation.type.toLowerCase()
  if (type.includes("whatsapp")) return "WhatsApp identifier"
  if (type.includes("telegram")) return "Telegram identifier"
  if (type.includes("email")) return "Email address"
  if (type.includes("phone")) return "Phone number"
  if (type === "claimed_brand_identity") return "Claimed brand"
  if (type.includes("payment")) return "Public payment observation"
  if (type.includes("offer")) return "Public offer claim"
  if (
    type.includes("outgoing") ||
    type.includes("redirect") ||
    type.includes("download")
  )
    return "Public destination"
  return titleCase(observation.type)
}

function runEvidenceCards(
  details: RunDetails,
  projection: GraphProjection
): EvidenceCardModel[] {
  const cards = details.source_case
    ? caseEvidenceCards(details.source_case, projection)
    : []
  for (const artifact of details.artifacts ?? []) {
    const preview = artifact.name.toLowerCase().endsWith(".png")
    cards.push({
      id: `run-artifact:${artifact.name}`,
      title: preview
        ? "Interaction screenshot"
        : titleCase(artifact.type || artifact.name),
      value: artifact.name,
      kind: "artifact",
      previewUrl: preview
        ? runArtifactUrl(details.workspace_id, artifact.name)
        : null,
      facts: [
        ["Artifact", artifact.name],
        ["Bytes", artifact.bytes],
        ["Type", artifact.type],
        ["Path", artifact.path],
      ],
    })
  }
  for (const lead of details.pending_leads ?? []) {
    const label = lead.url || lead.hostname || lead.lead_id || "Pending lead"
    const node = projection.nodes.find(
      (item) => item.label === label || item.label === hostnameFrom(label)
    )
    cards.push({
      id: `lead:${lead.lead_id || label}`,
      title: "Approval-gated candidate",
      value: label,
      kind: "candidate",
      nodeId: node?.id,
      facts: [
        ["Lead ID", lead.lead_id],
        ["Status", lead.status || details.lead_status],
        ["Relationship", "Not determined"],
        ["Collection", "Requires explicit human approval"],
      ],
    })
  }
  const assertions = details.assertions?.length
    ? details.assertions
    : details.assertion
      ? [details.assertion]
      : []
  for (const assertion of assertions) {
    const target = projection.edges.find(
      (edge) => edge.id === `assertion:${assertion.assertion_id}`
    )?.target
    cards.push(assertionCard(assertion, details, target))
  }
  for (const review of details.all_reviews ?? details.reviews ?? [])
    cards.push(reviewCard(review, projection))
  return cards
}

function assertionCard(
  assertion: AssertionRecord,
  details: RunDetails,
  nodeId?: string
): EvidenceCardModel {
  return {
    id: `assertion:${assertion.assertion_id}`,
    title: "Candidate assertion",
    value: `${assertion.subject || assertion.subject_node_id || "subject"} → ${assertion.object || assertion.object_node_id || "candidate"}`,
    kind: "assertion",
    occurredAt: assertion.created_at,
    nodeId,
    facts: [
      ["Assertion ID", assertion.assertion_id],
      ["Relation", titleCase(assertion.assertion_type)],
      [
        "Review",
        titleCase(
          details.assertion_statuses?.[assertion.assertion_id] ||
            details.current_assertion_status ||
            "needs review"
        ),
      ],
      ["Observations", assertion.supporting_observation_ids?.join(", ")],
      ["Artifacts", assertion.source_artifact_ids?.join(", ")],
      ["Limitations", assertion.limitations?.join(" · ")],
    ],
  }
}

function reviewCard(
  review: ReviewRecord,
  projection: GraphProjection
): EvidenceCardModel {
  return {
    id: `review:${review.review_id}`,
    title: "Human review decision",
    value: titleCase(review.outcome),
    kind: "review",
    occurredAt: review.occurred_at,
    nodeId: projection.edges.find(
      (edge) => edge.id === `assertion:${review.assertion_id}`
    )?.target,
    facts: [
      ["Review ID", review.review_id],
      ["Assertion", review.assertion_id],
      ["Reviewer label", review.reviewer_label],
      ["Outcome", titleCase(review.outcome)],
      ["Reason", review.reason],
      ["Version", `${review.previous_version} → ${review.new_version}`],
    ],
  }
}

function screenshotsForCase(
  details?: CaseDetails,
  selectedNode?: GraphNode | null
): ScreenshotChoice[] {
  if (!details) return []
  const attachedPage = selectedNode?.attributes.page as
    CaseDetails["pages"][number] | undefined
  const page =
    attachedPage ??
    details.pages.find((item) => `page:${item.id}` === selectedNode?.id) ??
    details.pages[0]
  if (!page) return []
  const labels: Array<[string | null | undefined, string]> = [
    [page.initial_screenshot_evidence_id, "Initial"],
    [page.screenshot_evidence_id, "Canonical"],
    [page.full_page_screenshot_evidence_id, "Full page"],
  ]
  const seen = new Set<string>()
  return labels.flatMap(([id, label]) => {
    if (!id || seen.has(id)) return []
    seen.add(id)
    const record = details.evidence.find((item) => item.id === id)
    return record ? [{ label, record }] : []
  })
}

function ScreenshotGallery({
  details,
  selectedNode,
}: {
  details?: CaseDetails
  selectedNode?: GraphNode | null
}) {
  const screenshots = screenshotsForCase(details, selectedNode)
  const preferred =
    screenshots.find((item) => item.label === "Full page") ??
    screenshots.find((item) => item.label === "Canonical") ??
    screenshots[0]
  const [selectedId, setSelectedId] = useState(preferred?.record.id)
  const selected =
    screenshots.find((item) => item.record.id === selectedId) ?? preferred
  if (!details || !selected) return null
  return (
    <figure className="screenshot-gallery">
      <div className="screenshot-frame">
        <img
          src={caseArtifactUrl(details.case_id, selected.record.id)}
          alt={`${selected.label} screenshot evidence for ${hostnameFrom(details.final_url_display)}`}
        />
        <figcaption>
          {selected.label} ·{" "}
          {selected.record.image_dimensions
            ? `${selected.record.image_dimensions.width} × ${selected.record.image_dimensions.height}`
            : "dimensions not recorded"}
        </figcaption>
      </div>
      <div className="screenshot-tabs">
        {screenshots.map((item) => (
          <Button
            key={item.record.id}
            size="sm"
            variant={
              item.record.id === selected.record.id ? "default" : "ghost"
            }
            onClick={() => setSelectedId(item.record.id)}
          >
            {item.label}
          </Button>
        ))}
      </div>
    </figure>
  )
}

function FactList({ facts }: { facts: Array<[string, unknown]> }) {
  return (
    <dl className="fact-list">
      {facts
        .filter(
          ([, value]) => value !== undefined && value !== null && value !== ""
        )
        .map(([label, value]) => (
          <div key={label}>
            <dt>{label}</dt>
            <dd>{String(value)}</dd>
          </div>
        ))}
    </dl>
  )
}

function selectedNodeFacts(node?: GraphNode | null): Array<[string, unknown]> {
  if (!node) return []
  const observation = node.attributes.observation as
    ObservationRecord | undefined
  const page = node.attributes.page as CaseDetails["pages"][number] | undefined
  if (node.presentation.visualKind === "page")
    return [
      ["Type", node.presentation.label],
      ["URL", node.label],
      ["Node state", titleCase(node.status)],
      ["Access", page?.access_outcome],
      ["Capture quality", page?.capture_adequacy],
      ["Extraction", page?.extraction_tier],
      ["Limitations", page?.limitation_reasons?.join(" · ") || "None recorded"],
    ]
  if (["contact", "brand"].includes(node.presentation.visualKind))
    return [
      ["Type", node.presentation.label],
      ["Observed value", observation?.display_value || node.label],
      ["Raw value", observation?.raw_value],
      ["Source page", observation?.source_page_id],
      ["Source artifact", observation?.source_artifact_id],
      ["Extraction", observation?.extraction_method],
      ["Context", observation?.surrounding_text],
      ["Review", "Observation only · no ownership attribution"],
    ]
  if (["transaction", "offer", "other"].includes(node.presentation.visualKind))
    return [
      ["Type", node.presentation.label],
      ["Category", node.attributes.claim_category],
      [
        "Values",
        (node.attributes.values as string[] | undefined)?.join(" · ") ||
          node.label,
      ],
      ["State", titleCase(node.status)],
      [
        "Meaning",
        "Publicly displayed claim; not a legal or ownership conclusion",
      ],
    ]
  return [
    ["Type", node.presentation.label],
    ["Destination", node.attributes.url || node.label],
    ["State", titleCase(node.status)],
    [
      "Relationship",
      node.attributes.relationship || "Candidate relationship not determined",
    ],
    ["Matched case", node.attributes.matched_case_id],
    ["Review", "Human review required for candidate relation"],
  ]
}

function EvidenceCard({
  card,
  expanded,
  onToggle,
}: {
  card: EvidenceCardModel
  expanded: boolean
  onToggle: () => void
}) {
  return (
    <article
      className={cn(
        "evidence-card",
        `evidence-kind-${card.kind}`,
        expanded && "evidence-card-expanded"
      )}
    >
      <button
        type="button"
        className="evidence-card-trigger"
        aria-expanded={expanded}
        onClick={onToggle}
      >
        <span className="evidence-card-icon">
          <CardIcon card={card} />
        </span>
        <span className="evidence-card-copy">
          <b>{card.title}</b>
          <strong>{card.value}</strong>
          <small>
            {valueOr(
              card.facts.find(([, value]) => value)?.[1],
              "Evidence-backed record"
            )}
          </small>
        </span>
        <time title={exactTime(card.occurredAt)}>
          {formatTime(card.occurredAt)}
        </time>
      </button>
      {expanded ? (
        <div className="evidence-card-detail">
          {card.previewUrl ? (
            <img
              src={card.previewUrl}
              alt={`${card.title} supporting screenshot`}
              loading="lazy"
            />
          ) : null}
          <FactList facts={card.facts} />
        </div>
      ) : null}
    </article>
  )
}

function InspectorHeader({
  node,
  source,
}: {
  node?: GraphNode | null
  source: EvidenceSource
}) {
  const run = source.kind === "run" ? source.details : undefined
  const standaloneCase = source.kind === "case" ? source.details : undefined
  const fallback = run
    ? run.seed_url || run.case_id
    : standaloneCase?.final_url_display ||
      standaloneCase?.case_id ||
      "saved evidence"
  return (
    <header className="inspector-heading">
      <span>{node?.presentation.label || "Evidence package"}</span>
      <h2>{node?.label || hostnameFrom(fallback)}</h2>
      <p>
        {node?.status === "lead"
          ? "Relationship: not determined. This candidate requires explicit collection approval or human review."
          : "Every displayed fact resolves to a verified local artifact, deterministic observation, or persisted event."}
      </p>
    </header>
  )
}

function ReviewForm({ run }: { run: RunDetails }) {
  const queryClient = useQueryClient()
  const [reviewer, setReviewer] = useState("")
  const [outcome, setOutcome] = useState("verified")
  const [reason, setReason] = useState("")
  const assertion = run.assertion
  const mutation = useMutation({
    mutationFn: () => {
      if (!assertion) throw new Error("No reviewable assertion is available")
      return api.appendReview(run.workspace_id, {
        assertion_id: assertion.assertion_id,
        outcome,
        reviewer_label: reviewer.trim(),
        reason: reason.trim(),
      })
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({
        queryKey: ["run", run.workspace_id],
      })
      toast.success("Append-only review version saved")
      setReason("")
    },
    onError: (error) => toast.error(error.message),
  })
  if (!assertion) return null
  return (
    <form
      className="review-form"
      onSubmit={(event) => {
        event.preventDefault()
        mutation.mutate()
      }}
    >
      <Label htmlFor="reviewer">Reviewer label</Label>
      <Input
        id="reviewer"
        required
        maxLength={200}
        value={reviewer}
        onChange={(event) => setReviewer(event.target.value)}
      />
      <Label htmlFor="outcome">Decision</Label>
      <Select
        value={outcome}
        onValueChange={(value) => setOutcome(value ?? "verified")}
      >
        <SelectTrigger id="outcome">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          {[
            "verified",
            "rejected",
            "needs_more_evidence",
            "duplicate",
            "uncertain",
          ].map((value) => (
            <SelectItem key={value} value={value}>
              {titleCase(value)}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
      <Label htmlFor="reason">Evidence-bounded reason</Label>
      <Textarea
        id="reason"
        required
        maxLength={2000}
        value={reason}
        onChange={(event) => setReason(event.target.value)}
      />
      <Button type="submit" disabled={mutation.isPending}>
        {mutation.isPending ? "Saving review…" : "Append review decision"}
      </Button>
    </form>
  )
}

function EventInspector({ event }: { event: InvestigationEvent }) {
  const payload = Object.entries(event.payload ?? {})
    .filter(([, value]) => value !== undefined)
    .slice(0, 16)
  return (
    <section className="inspector-section">
      <h3>
        <Code weight="duotone" /> Persisted event
      </h3>
      <FactList
        facts={[
          ["Kind", titleCase(event.kind)],
          ["Sequence", event.sequence],
          ["Occurred", exactTime(event.occurred_at)],
          ["Event ID", event.event_id],
          ["Causation", event.causation_event_id],
          ["Schema", event.schema_version],
          ...payload,
        ]}
      />
    </section>
  )
}

export function EvidenceInspector({
  source,
  projection,
  selectedNode,
  selectedEvent,
  onFocusNode,
}: {
  source: EvidenceSource
  projection: GraphProjection
  selectedNode?: GraphNode | null
  selectedEvent?: InvestigationEvent | null
  onFocusNode: (nodeId: string) => void
}) {
  const queryClient = useQueryClient()
  const [query, setQuery] = useState("")
  const deferredQuery = useDeferredValue(query)
  const [expandedId, setExpandedId] = useState<string | null>(null)
  const caseDetails = sourceCase(source)
  const cards = useMemo(
    () =>
      source.kind === "case"
        ? caseEvidenceCards(source.details, projection)
        : runEvidenceCards(source.details, projection),
    [projection, source]
  )
  const filteredCards = useMemo(() => {
    const normalized = deferredQuery.trim().toLowerCase()
    if (!normalized) return cards
    return cards.filter((card) =>
      `${card.title} ${card.value} ${card.facts.flat().join(" ")}`
        .toLowerCase()
        .includes(normalized)
    )
  }, [cards, deferredQuery])
  const run = source.kind === "run" ? source.details : undefined
  const standaloneCase = source.kind === "case" ? source.details : undefined
  const approve = useMutation({
    mutationFn: () =>
      run
        ? api.approveCandidate(run.workspace_id)
        : Promise.reject(new Error("No run selected")),
    onSuccess: async () => {
      if (run)
        await queryClient.invalidateQueries({
          queryKey: ["run", run.workspace_id],
        })
      toast.success("Approval recorded before bounded candidate collection")
    },
    onError: (error) => toast.error(error.message),
  })
  const activeCardId =
    expandedId ??
    cards.find((card) => card.nodeId === selectedNode?.id)?.id ??
    null

  const artifactLinks =
    source.kind === "run"
      ? [
          ...(source.details.source_case?.evidence ?? []).map((record) => ({
            label: record.id,
            href: caseArtifactUrl(
              source.details.source_case?.case_id ?? "",
              record.id
            ),
          })),
          ...(source.details.artifacts ?? []).map((artifact) => ({
            label: artifact.name,
            href: runArtifactUrl(source.details.workspace_id, artifact.name),
          })),
        ]
      : source.details.evidence.map((record) => ({
          label: record.id,
          href: caseArtifactUrl(source.details.case_id, record.id),
        }))

  return (
    <aside className="evidence-inspector" aria-label="Evidence inspector">
      <Tabs defaultValue="evidence" className="inspector-tabs">
        <TabsList className="inspector-tab-list">
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="evidence">Evidence</TabsTrigger>
          <TabsTrigger value="artifacts">Artifacts</TabsTrigger>
          <TabsTrigger value="technical">Technical</TabsTrigger>
        </TabsList>

        <TabsContent value="overview" className="inspector-tab-content">
          <ScrollArea className="inspector-scroll">
            <InspectorHeader node={selectedNode} source={source} />
            <ScreenshotGallery
              details={caseDetails}
              selectedNode={selectedNode}
            />
            <section className="inspector-section">
              <h3>
                <Globe weight="duotone" /> Selected node
              </h3>
              <FactList facts={selectedNodeFacts(selectedNode)} />
            </section>
            <section className="inspector-section">
              <h3>
                <ShieldWarning weight="duotone" /> Interpretation
              </h3>
              <p className="boundary-copy">
                Observations show what a public page displayed. They do not
                establish ownership, identity, criminality, or legal status.
              </p>
            </section>
          </ScrollArea>
        </TabsContent>

        <TabsContent value="evidence" className="inspector-tab-content">
          <div className="inspector-search">
            <MagnifyingGlass />
            <Input
              type="search"
              placeholder="Find evidence, entity, relation…"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
            />
          </div>
          <ScrollArea className="inspector-scroll">
            <InspectorHeader node={selectedNode} source={source} />
            <ScreenshotGallery
              details={caseDetails}
              selectedNode={selectedNode}
            />
            {selectedEvent ? <EventInspector event={selectedEvent} /> : null}
            <section className="inspector-section evidence-catalog-section">
              <h3>
                <BinocularsIcon /> Evidence and claims{" "}
                <Badge variant="outline">{filteredCards.length}</Badge>
              </h3>
              <div className="evidence-card-list">
                {filteredCards.map((card) => (
                  <EvidenceCard
                    key={card.id}
                    card={card}
                    expanded={activeCardId === card.id}
                    onToggle={() => {
                      setExpandedId(activeCardId === card.id ? null : card.id)
                      if (card.nodeId) onFocusNode(card.nodeId)
                    }}
                  />
                ))}
                {!filteredCards.length ? (
                  <p className="boundary-copy">
                    No evidence cards match this search.
                  </p>
                ) : null}
              </div>
            </section>
            {run?.lead_status === "waiting_for_approval" ? (
              <section className="inspector-section approval-boundary">
                <h3>
                  <ShieldWarning weight="duotone" /> Approval boundary
                </h3>
                <p>
                  Collect one directly observed candidate page only after an
                  explicit approval event is persisted.
                </p>
                <Button
                  variant="outline"
                  disabled={approve.isPending}
                  onClick={() => approve.mutate()}
                >
                  {approve.isPending
                    ? "Collecting approved page…"
                    : "Approve candidate collection"}
                </Button>
              </section>
            ) : null}
            {run?.assertion ? (
              <section className="inspector-section">
                <h3>
                  <SealCheck weight="duotone" /> Append human review
                </h3>
                <ReviewForm run={run} />
              </section>
            ) : null}
          </ScrollArea>
        </TabsContent>

        <TabsContent value="artifacts" className="inspector-tab-content">
          <ScrollArea className="inspector-scroll">
            <header className="inspector-heading">
              <span>VERIFIED MANIFEST</span>
              <h2>Saved evidence files</h2>
              <p>
                Each link resolves through the local verified artifact route.
              </p>
            </header>
            <section className="inspector-section artifact-link-list">
              {artifactLinks.map((item) => (
                <a key={item.href} href={item.href}>
                  <File weight="duotone" />
                  <span>{item.label}</span>
                  <ArrowSquareOut />
                </a>
              ))}
            </section>
          </ScrollArea>
        </TabsContent>

        <TabsContent value="technical" className="inspector-tab-content">
          <ScrollArea className="inspector-scroll">
            <header className="inspector-heading">
              <span>TECHNICAL ENVELOPE</span>
              <h2>Bounded runtime</h2>
              <p>
                Implementation state and limitations, not a relationship
                conclusion.
              </p>
            </header>
            <section className="inspector-section">
              <FactList
                facts={[
                  ["Source", run?.source_kind || "deterministic case"],
                  ["Case ID", run?.case_id || standaloneCase?.case_id],
                  ["Workspace", run?.workspace_id],
                  ["Persisted events", run?.events.length ?? 0],
                  ["Agent steps", run?.agent_steps ?? 0],
                  ["Pending review", run?.pending_review_count ?? 0],
                ]}
              />
            </section>
          </ScrollArea>
        </TabsContent>
      </Tabs>
    </aside>
  )
}

function BinocularsIcon() {
  return <Browser weight="duotone" />
}
