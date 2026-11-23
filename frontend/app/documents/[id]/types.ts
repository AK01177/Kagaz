export type ActiveTab = "overview" | "validation" | "audit" | "assistant";

export interface ExtractionResult {
  document_id: string;
  document_type: string | null;
  fields: Record<string, string | number | string[]>;
  confidence: Record<string, number>;
  status: string;
  ocr_text_length?: number;
}

export interface PolicyValidationSource {
  reference_type?: string;
  policy_id?: string;
  policy_name?: string;
  policy_version?: string;
  section?: string;
  page_number?: number;
  excerpt: string;
  supporting_quote?: string;
}

export interface PolicyValidationFinding {
  id: string;
  status: "PASS" | "FLAG" | "FAIL" | "NEEDS_HUMAN_REVIEW" | "MISSING_INFORMATION";
  requirement: string;
  explanation: string;
  field_name?: string | null;
  document_value?: string | null;
  confidence?: number | null;
  sources: PolicyValidationSource[];
}

export interface PolicyValidationRun {
  id: string;
  document_id: string;
  status: "PASS" | "FLAG" | "FAIL" | "NEEDS_HUMAN_REVIEW";
  summary: string;
  retrieval_outcome: string;
  policy_versions: Array<{
    id?: string;
    policy_name?: string;
    version?: string;
    domain?: string;
  }>;
  findings: PolicyValidationFinding[];
  created_at: string;
}

export interface AuditEvent {
  id: string;
  action: string;
  actor_id?: string | null;
  details?: Record<string, unknown> | null;
  created_at: string;
}

export interface AssistantSource {
  source_type: "DOCUMENT_FIELD" | "POLICY_CHUNK" | "VALIDATION_FINDING" | string;
  title: string;
  reference: string;
  excerpt: string;
  policy_name?: string | null;
  policy_version?: string | null;
  section?: string | null;
  page_number?: number | null;
}

export interface AssistantMessage {
  id: string;
  sender: "user" | "assistant";
  content: string;
  timestamp: string;
  sources?: AssistantSource[];
  is_grounded?: boolean;
  limitation?: string | null;
  confidence?: number | null;
}
