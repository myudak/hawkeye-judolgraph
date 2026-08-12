export type EvidenceState = "verified" | "pending" | "rejected";
export type EvidenceKind =
  "domain" | "page" | "telegram" | "phone" | "whatsapp";

export interface EvidenceNodeData {
  id: string;
  label: string;
  detail: string;
  kind: EvidenceKind;
  x: number;
  y: number;
  step: number;
  source: string;
  state: EvidenceState;
}

export interface EvidenceEdgeData {
  id: string;
  source: string;
  target: string;
  label: string;
  state: EvidenceState;
  step: number;
}
