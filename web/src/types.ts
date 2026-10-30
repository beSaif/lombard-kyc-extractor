// Types derived from the live API and a real run (runs/<id>/result.json).

export type Tier = "clean" | "scan" | "photo";
/** Where a case lives: a quality tier of the synthetic set, or "upload" for your own documents. */
export type CaseTier = Tier | "upload";
export type Suite = "standard" | "hard" | "blind" | "real";
export type DocType = "passport" | "form_a" | "proof_of_address";
export type EvidenceStatus = "verified" | "unverified" | "corroborated" | "dropped" | "out_of_place";
export type Decision = "pre_filled_review" | "manual_review";

export interface CaseSummary {
  tier: Tier;
  case: string;
  suite?: Suite;
  defects: string[];
  traps: string[];
  layouts: Record<string, string>;
  files: string[];
}

export interface Truth {
  case: string;
  tier: Tier;
  defects: string[];
  expected_flags: string[];
  expected_checks?: string[];
  suite?: Suite;
  traps: string[];
  layouts: Record<string, string>;
  as_of?: string;
  fields: Record<DocType, Record<string, string | null>>;
}

export interface CaseDetail {
  truth: Truth | null; // null for an upload
  files: string[];
}

export interface Extractor {
  spec: string;
  provider: "rules" | "openai" | "ollama" | string;
  model: string;
  mode: "text" | "vision" | "both";
  local: boolean;
  price?: [number, number] | null;
}

export interface FieldValue {
  value: string | null;
  quote: string | null;
  page: number | null;
}

export interface Evidence {
  method: "exact" | "fuzzy" | "mrz_pass" | "checksum" | "not_found" | string;
  basis?: "text_layer" | "ocr" | "checksum" | null; // what the evidence rests on
  score: number | null;
  page: number | null;
  bbox: [number, number, number, number] | null;
  matched_text: string | null;
  status: EvidenceStatus;
  value: string | null;
  why?: string;
  corroborated_by?: string;
  // where the quote sits on the page (kyc_demo/anchor.py)
  place?: {
    verdict: "anchored" | "no_label" | "other_field" | "other_section" | "fine_print";
    label: string | null;
    label_field: string | null;
    label_bbox: [number, number, number, number] | null;
    height_ratio: number | null;
  };
}

export interface Check {
  name: string;
  label: string;
  passed: boolean | null;
  detail: string;
  flag: string;
  severity: string;
  inputs: Record<string, any>;
}

export interface Flag {
  code: string;
  severity: string;
  message: string;
  check: string;
}

export interface Word {
  t: string;
  b: [number, number, number, number];
  c: number | null;
}

export type StepKind =
  | "load"
  | "preprocess"
  | "read"
  | "prompt"
  | "llm"
  | "normalise"
  | "extract"
  | "ground"
  | "cross_model"
  | "validate"
  | "corroborate"
  | "signature"
  | "route";

export interface Step {
  id: number;
  kind: StepKind | string;
  title: string;
  doc: DocType | null;
  code: string[];
  explain: string;
  status: "ok" | "error";
  ms: number | null; // null while the step is still running
  data: Record<string, any>;
}

export interface Totals {
  seconds: number;
  model_seconds: number;
  input_tokens: number;
  output_tokens: number;
  cost_usd: number | null;
}

export interface Usage {
  input_tokens?: number | null;
  output_tokens?: number | null;
  reasoning_tokens?: number | null;
  seconds?: number | null;
  cost_usd?: number | null;
}

export interface FieldScore {
  ok: boolean;
  got: string | null;
  want: string | null;
}

export interface CaseScore {
  case: string;
  tier: Tier;
  defects: string[];
  traps: string[];
  layouts: Record<string, string>;
  decision: Decision;
  raised: string[];
  expected: string[];
  fields: Record<string, FieldScore>;
  evidence: Record<string, Record<string, EvidenceStatus>>;
  totals: Totals;
  error?: undefined;
}

export interface CaseError {
  case: string;
  tier: Tier;
  error: string;
}

export interface RunRequest {
  tier: CaseTier;
  case: string;
  extractor: string;
  second?: string | null;
  reader: "auto" | "text" | "ocr";
  as_of?: string;
}

export interface Result {
  case: string;
  tier: CaseTier | string;
  extractor: string;
  second: string | null;
  reader: string;
  as_of: string;
  decision: Decision;
  flags: Flag[];
  checks: Check[];
  fields: Record<DocType, Record<string, FieldValue> | null>;
  evidence: Record<DocType, Record<string, Evidence>>;
  usage: Record<string, Usage>;
  totals: Totals;
  score?: CaseScore; // absent for uploads: there is no truth to score against
  steps: Step[];
  run_id: string;
  request: RunRequest;
}

export interface RunState {
  run_id: string;
  status: "running" | "done" | "error";
  request?: RunRequest;
  steps?: Step[];
  result?: Result;
  elapsed?: number;
  error?: string;
}

export interface RunListItem {
  run_id: string;
  tier: CaseTier;
  case: string;
  extractor: string;
  second: string | null;
  decision: Decision;
  flags: string[];
  totals: Totals;
  review?: ReviewStatus;
}

export type ReviewStatus = "open" | "awaiting_second_approval" | "approved" | "rejected" | "info_requested";

export interface AuditEntry {
  seq: number;
  at: string;
  kind: "field" | "decision";
  run_id: string;
  reviewer: string;
  doc?: string;
  field?: string;
  action?: "accept" | "correct" | "reject";
  value?: string | null;
  model_value?: string | null;
  reason?: string | null;
  decision?: "approve" | "reject" | "request_info";
  note?: string | null;
  documents?: Record<string, string>;
  prompt_version?: string | null;
  prev: string;
  hash: string;
}

export interface ReviewState {
  status: ReviewStatus;
  approved_by: string[];
  fields: Record<string, AuditEntry>; // "doc.field" -> the latest decision on it
  needs_eyes: Record<string, "unverified" | "dropped" | "out_of_place" | "missing">;
  pending: string[];
  rejected_fields: string[];
  entries: AuditEntry[];
}

export interface CodeRef {
  ref: string;
  file: string;
  start: number;
  end: number;
  source: string;
  doc: string | null;
}

export interface ModuleSource {
  module: string;
  file: string;
  lines: number;
  doc: string | null;
  source: string;
}

export interface Summary {
  files: number;
  field_accuracy: number | null;
  critical_field_accuracy: number | null;
  defect_recall: number | null;
  defect_recall_ci?: [number, number] | null;
  defect_recall_n?: [number, number];
  defects_not_flagged?: number | null;
  right_check_rate?: number | null;
  defect_precision: number | null;
  missed_defect_files: number | null;
  errors?: number;
  defect_files: number | null;
  straight_through_rate: number | null;
  routing_accuracy: number | null;
  trap_false_alarm_rate: number | null;
  process_flags_per_file: number | null;
  seconds_per_file: number | null;
  cost_per_file_usd: number | null;
  fields: Record<string, number | null>;
  per_defect: Record<string, number | null>;
  per_trap: Record<string, number | null>;
}

export interface EvalReport {
  extractor: string;
  suite?: Suite;
  as_of: string;
  tiers: Partial<Record<Tier, Summary>>;
  cases: Partial<Record<Tier, (CaseScore | CaseError)[]>>;
}

/** One region of a page a reviewer should look at (kyc_demo/issues.py). bbox is in 0..1 page fractions. */
export interface IssueRegion {
  doc: DocType;
  field: string | null;
  label: string;
  page: number;
  bbox: [number, number, number, number] | null;
  value: string | null;
  status: EvidenceStatus | null;
  note: string | null;
  exact: boolean; // false: no box, or only the closest text OCR found
}

export interface Issue {
  id: number;
  code: string;
  severity: string;
  check: string;
  title: string;
  message: string;
  missing_doc: DocType | null;
  regions: IssueRegion[];
}

export interface RunIssues {
  run_id: string;
  decision: Decision;
  issues: Issue[];
  pages: Partial<Record<DocType, { page: number; image: string }[]>>;
}
