export type Model = { id: string; input_usd_per_million: number; output_usd_per_million: number; settings: Record<string, unknown>; [key: string]: unknown }
export type Policy = {
  schema_version: number; id: string; adapter: string; models: Model[];
  limits: { deadline_seconds: number; model_steps: number; output_tokens: number; request_bytes: number; tool_calls: number; transport_retries: number; [key: string]: unknown };
  parser_version: string; validator_version: string; price_source: string; prices_verified_at: string; supporting_report: string | null; [key: string]: unknown;
}
export type ToolEvent = { kind: string; tool?: string; arguments?: Record<string, unknown>; result?: unknown; raw_arguments?: string; code?: string; message?: string; [key: string]: unknown }
export type Attempt = {
  model: string; verdict: string; resolution: string; result: Record<string, unknown> | null;
  failure_context: { reason: string; observations: { code: string; field?: string | null; tool?: string | null }[]; restart_from_original_state?: boolean } | null;
  events: ToolEvent[]; duration_ms: number;
  usage?: { estimated_usd: number | null; input_tokens?: number | null; output_tokens?: number | null; status: string; duration_ms: number }[];
}
export type StateRow = Record<string, unknown>
export type StoreState = { lines?: StateRow[]; orders?: StateRow[]; products?: StateRow[]; stock?: StateRow[]; [key: string]: unknown }
export type Run = {
  id: string; source: string; task: { id: string; request: string; family: string; split: string; template_group?: string; [key: string]: unknown };
  policy: Policy; policy_hash?: string; attempts: Attempt[]; verdict: string; resolution: string;
  outcome: { success: boolean; critical_error: boolean; checks: Record<string, boolean> } | null;
  before: StoreState; after: StoreState; total_estimated_usd: number | null; duration_ms: number;
  measurement_complete: boolean; repetition: number;
}
export type Summary = {
  id: string; assigned: number; completed: number; successes: number; success_rate: number;
  total_estimated_usd: number | null; cost_per_success: number | null;
  p95_ms: number | null; median_ms: number | null; escalation_rate: number;
  incorrect_accepted: string[]; incorrect_accepted_mutations?: string[]; critical_errors: number; incomplete_measurements: number;
  savings_vs_ultra: number | null; savings_vs_single: number | null;
  normalization_rate: number; rejection_rate: number; qualifies: boolean;
}
export type Report = {
  schema_version: number; id: string; created_at: string; source: string; split: string; manifest_hash: string;
  provenance: { limitations?: string; evaluation_disclosure?: string; protocol_version?: string | number; paired?: { policy: string; task_id: string; repetition: number; success: boolean; ultra_success: boolean }[]; [key: string]: unknown };
  policies: Summary[]; runs: Run[]; recommendation: { selected: string | null; status: string; reason: string };
}
export type Catalog = { tasks: string[]; policies: string[]; schema_version: number; configurations: Record<string, Policy>; policy_hashes: Record<string, string>; available: boolean; message?: string }
export type ReportEntry = { file: string; label: string }
