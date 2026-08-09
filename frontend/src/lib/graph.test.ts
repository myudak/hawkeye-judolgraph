import { describe, expect, it } from "vitest"

import type { CaseDetails, RunDetails } from "@/api/types"
import {
  buildCaseProjection,
  buildRunProjection,
  presentationFor,
} from "@/lib/graph"

const caseFixture = {
  case_id: "case-fixture",
  integrity: "verified",
  started_at: "2026-08-09T10:00:00Z",
  completed_at: "2026-08-09T10:00:10Z",
  seed_url_display: "https://example.invalid/",
  final_url_display: "https://example.invalid/",
  capture_adequacy: "adequate",
  extraction_tier: "verified",
  pages: [
    {
      id: "page-001",
      final_url_display: "https://example.invalid/",
      capture_adequacy: "adequate",
      screenshot_evidence_id: "shot-001",
    },
  ],
  frontier: [],
  evidence: [
    {
      id: "shot-001",
      type: "screenshot",
      page_id: "page-001",
      collected_at: "2026-08-09T10:00:08Z",
      artifact_available: true,
    },
  ],
  observations: [
    {
      id: "obs-wa",
      type: "public_whatsapp_link",
      display_value: "+62000000000",
      source_page_id: "page-001",
      source_artifact_id: "page-html",
    },
    {
      id: "obs-brand",
      type: "claimed_brand_identity",
      display_value: "Example Brand",
      source_page_id: "page-001",
      source_artifact_id: "page-html",
    },
    {
      id: "obs-offer",
      type: "public_offer_claim",
      display_value: "public offer",
      source_page_id: "page-001",
      source_artifact_id: "page-html",
    },
    {
      id: "obs-payment",
      type: "public_payment_method",
      display_value: "public payment",
      source_page_id: "page-001",
      source_artifact_id: "page-html",
    },
  ],
  candidates: [],
} as CaseDetails

describe("graph projections", () => {
  it("keeps page, contact, brand, offer, and transaction taxonomy separate", () => {
    const projection = buildCaseProjection(caseFixture)
    const kinds = new Set(
      projection.nodes.map((node) => node.presentation.visualKind)
    )

    expect(kinds).toEqual(
      new Set(["page", "contact", "brand", "offer", "transaction"])
    )
    expect(
      projection.nodes.find(
        (node) => node.presentation.visualKind === "contact"
      )?.label
    ).toBe("+62000000000")
    expect(projection.edges.every((edge) => edge.source && edge.target)).toBe(
      true
    )
  })

  it("keeps candidates explicitly relationship-neutral", () => {
    const presentation = presentationFor({
      kind: "candidate_domain",
      attributes: {},
    })

    expect(presentation.visualKind).toBe("candidate")
    expect(presentation.label).toBe("Candidate")
  })

  it("reduces persisted run events into a compact replay timeline", () => {
    const run = {
      workspace_id: "run-fixture",
      case_id: "case-fixture",
      run_id: "run-001",
      events: [
        {
          event_id: "event-1",
          sequence: 1,
          kind: "run.started",
          occurred_at: "2026-08-09T10:00:00Z",
          payload: {},
        },
        {
          event_id: "event-2",
          sequence: 2,
          kind: "observation.created",
          occurred_at: "2026-08-09T10:00:02Z",
          payload: {},
        },
        {
          event_id: "event-3",
          sequence: 3,
          kind: "observation.created",
          occurred_at: "2026-08-09T10:00:03Z",
          payload: {},
        },
        {
          event_id: "event-4",
          sequence: 4,
          kind: "run.completed",
          occurred_at: "2026-08-09T10:00:04Z",
          payload: {},
        },
      ],
      graph: {
        nodes: [
          {
            id: "page:seed",
            kind: "seed_page",
            label: "https://example.invalid/",
            status: "collected",
            attributes: {},
          },
        ],
        edges: [],
        animations: [{ target_id: "page:seed", sequence: 1 }],
      },
      artifacts: [],
    } as RunDetails

    const projection = buildRunProjection(run)

    expect(projection.timeline.map((item) => item.label)).toEqual([
      "Investigation started",
      "Semantic evidence extracted",
      "Investigation completed",
    ])
    expect(projection.timeline[1].detail).toBe("2 evidence-backed observations")
  })
})
