// Mirrors apps/api/src/trialready_api/schemas/{api.py,gap_report.py} exactly.
// Kept hand-in-sync deliberately rather than codegen'd from the OpenAPI schema —
// worth revisiting (openapi-typescript) once the API surface stops changing
// weekly; not worth the build-step complexity yet for four endpoints.

export interface Site {
  id: string;
  name: string;
  principal_investigator_name: string;
  contact_email: string;
  created_at: string;
}

export interface SiteCreate {
  name: string;
  principal_investigator_name: string;
  contact_email: string;
}

export interface Protocol {
  id: string;
  site_id: string;
  sponsor_name: string;
  protocol_number: string;
  title: string;
  created_at: string;
}

export interface ProtocolCreate {
  sponsor_name: string;
  protocol_number: string;
  title: string;
}

export type DocumentStatus =
  | "pending_extraction"
  | "pending_human_review"
  | "accepted"
  | "rejected"
  | "superseded";

export interface BinderDocument {
  id: string;
  document_type_id: string;
  original_filename: string;
  status: DocumentStatus;
  classification_confidence: number | null;
  extracted_effective_date: string | null;
  extracted_expiry_date: string | null;
  uploaded_at: string;
}

export type GapSeverity = "missing" | "expired" | "expiring_soon" | "outdated_version" | "pending_review";

export interface GapItem {
  document_type_id: string;
  document_name: string;
  severity: GapSeverity;
  detail: string;
  regulatory_basis: string;
  due_date: string | null;
  existing_document_id: string | null;
}

export interface GapReport {
  protocol_id: string;
  generated_at: string;
  total_required: number;
  total_satisfied: number;
  items: GapItem[];
  // Computed server-side by the same rules engine that produced `items` (see
  // services/rules_engine.py) — deliberately NOT recomputed here. The frontend
  // has no business re-deriving a compliance determination from raw severities;
  // it just displays what the one place that owns this decision said.
  is_monitor_visit_ready: boolean;
}
