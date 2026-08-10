export type IntegrityState = "verified" | "error"

export interface CaseListItem {
  case_id: string
  integrity: IntegrityState
  status?: string
  started_at?: string | null
  completed_at?: string | null
  page_title?: string | null
  seed_url_display?: string | null
  final_url_display?: string | null
  capture_outcome?: string | null
  access_outcome?: string | null
  capture_adequacy?: string | null
  extraction_tier?: string | null
  public_status?: string | null
  page_count?: number
  candidate_count?: number
  gambling_indicator_count?: number
  error?: string
}

export interface RunListItem {
  workspace_id: string
  case_id: string
  run_id: string
  lead_status?: string | null
  agent_mode?: string | null
  agent_model?: string | null
  source_kind?: string | null
  source_case_id?: string | null
  seed_url?: string | null
  investigation_name?: string | null
  investigation_mode?: string | null
  capture_adequacy?: string | null
  extraction_tier?: string | null
  agent_stop_reason?: string | null
  agent_steps?: number
  updated_at?: string | null
}

export interface PageRecord {
  id: string
  depth?: number
  state?: string
  final_url_display?: string
  capture_outcome?: string
  access_outcome?: string
  capture_adequacy?: string
  extraction_eligible?: boolean
  extraction_tier?: string
  extraction_skip_reason?: string | null
  public_status?: string
  limitation_reasons?: string[]
  html_evidence_id?: string | null
  screenshot_evidence_id?: string | null
  initial_screenshot_evidence_id?: string | null
  full_page_screenshot_evidence_id?: string | null
  visible_text_evidence_id?: string | null
  readiness_evidence_id?: string | null
}

export interface EvidenceRecord {
  id: string
  type: string
  source_url_display?: string
  collected_at?: string | null
  sha256?: string
  page_id?: string
  artifact_available?: boolean
  image_dimensions?: { width: number; height: number } | null
}

export interface ObservationRecord {
  id: string
  type: string
  display_value: string
  raw_value?: string
  source_page_id?: string
  source_artifact_id?: string
  screenshot_evidence_id?: string | null
  crop_evidence_id?: string | null
  surrounding_text?: string | null
  confidence?: number | null
  evidence_strength?: string | null
  extraction_method?: string | null
  limitations?: string[]
}

export interface CandidateRecord {
  id?: string
  candidate_id?: string
  hostname: string
  url?: string
  state?: string
  reasons?: Array<Record<string, unknown>>
}

export interface IndicatorClassification {
  observation_id: string
  label: string
  category?: string
  display_value?: string
  matched_terms?: string[]
  source_artifact_id?: string
  screenshot_evidence_id?: string
}

export interface IndicatorSummary {
  status?: string
  policy_version?: string
  indicator_count: number
  reviewed_observation_count?: number
  category_counts?: Record<string, number>
  osint_counts?: Record<string, number>
  classifications?: IndicatorClassification[]
  limitations?: string[]
}

export interface FrontierRecord {
  normalized_url_display?: string
  source_page_id?: string
  discovery_method?: string
}

export interface CaseDetails extends CaseListItem {
  seed_url_display?: string
  content_usable?: boolean
  extraction_eligible?: boolean
  extraction_skip_reason?: string | null
  limitation_reasons?: string[]
  pages: PageRecord[]
  frontier?: FrontierRecord[]
  evidence: EvidenceRecord[]
  observations: ObservationRecord[]
  candidates: CandidateRecord[]
  gambling_indicators?: IndicatorSummary
}

export interface InvestigationEvent {
  event_id: string
  sequence: number
  case_id?: string
  run_id?: string
  kind: string
  occurred_at?: string | null
  causation_event_id?: string | null
  schema_version?: string
  payload?: Record<string, unknown>
}

export interface RawGraphNode {
  id: string
  kind: string
  label: string
  status?: string
  attributes?: Record<string, unknown>
}

export interface RawGraphEdge {
  id: string
  source: string | { id: string }
  target: string | { id: string }
  relation?: string
  type?: string
  appearance?: string
  supporting_event_ids?: string[]
  evidence?: Record<string, unknown> | null
}

export interface GraphAnimation {
  target_id: string
  sequence: number
}

export interface ArtifactRecord {
  name: string
  bytes?: number
  type?: string
  path?: string
}

export interface PendingLead {
  lead_id?: string
  url?: string
  hostname?: string
  status?: string
}

export interface AssertionRecord {
  assertion_id: string
  assertion_type?: string
  subject?: string
  object?: string
  subject_node_id?: string
  object_node_id?: string
  created_at?: string
  supporting_observation_ids?: string[]
  source_artifact_ids?: string[]
  limitations?: string[]
}

export interface ReviewRecord {
  review_id: string
  assertion_id: string
  reviewer_label?: string
  outcome: string
  reason?: string
  occurred_at?: string
  previous_version?: number
  new_version?: number
}

export interface RunDetails extends RunListItem {
  agent_stop_reason?: string | null
  candidate_case_id?: string | null
  action_summary?: Record<string, unknown> | null
  action_summaries?: Array<Record<string, unknown>>
  pending_leads?: PendingLead[]
  assertion?: AssertionRecord | null
  assertions?: AssertionRecord[]
  assertion_statuses?: Record<string, string>
  current_assertion_status?: string | null
  reviews?: ReviewRecord[]
  all_reviews?: ReviewRecord[]
  pending_review_count?: number
  events: InvestigationEvent[]
  graph: {
    nodes: RawGraphNode[]
    edges: RawGraphEdge[]
    animations?: GraphAnimation[]
    timeline?: Array<Record<string, unknown>>
  }
  artifacts: ArtifactRecord[]
  source_case?: CaseDetails | null
  candidate_case?: CaseDetails | null
  gambling_indicators?: IndicatorSummary
}

export type EvidenceSource =
  | { kind: "case"; id: string; details: CaseDetails }
  | { kind: "run"; id: string; details: RunDetails }

export interface CapabilityStatus {
  state: string
  selected_model?: string | null
  safe_to_enable_model_path?: boolean
}

export interface JobHistoryItem {
  stage: string
  at?: string
}

export interface JobPreview {
  preview_id: string
  revision: number
  page_id: string
  kind: "canonical" | "agent_before" | "agent_after"
  verification: "transient" | "persisted" | "verified"
  url?: string | null
  captured_at?: string | null
  width?: number | null
  height?: number | null
}

export interface JobAgentFocus {
  status: "selected" | "completed" | "evidence_extracted" | "blocked"
  label?: string | null
  tool_name?: string | null
  iteration?: number
  target_preview_revision?: number
  result_preview_revision?: number
  added_observation_count?: number
  reason?: string | null
  target_bbox?: {
    x: number
    y: number
    width: number
    height: number
  } | null
  viewport?: {
    width?: number | null
    height?: number | null
  } | null
}

export interface JobVisualState {
  revision: number
  previews: JobPreview[]
  latest_preview?: JobPreview | null
  agent_focus?: JobAgentFocus | null
}

export interface InvestigationJob {
  job_id: string
  status: "queued" | "running" | "completed" | "failed"
  stage: string
  started_at: string
  updated_at?: string
  deadline_seconds: number
  detail?: Record<string, unknown>
  history?: JobHistoryItem[]
  error?: string | null
  result?: RunDetails | null
  visual_state?: JobVisualState
}
