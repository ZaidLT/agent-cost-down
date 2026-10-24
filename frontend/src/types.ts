export type Policy = {
  schema_version: number; id: string; adapter: string; models: {id: string}[];
  limits: {deadline_seconds: number}; supporting_report: string | null;
}
export type Attempt = {
  model: string; verdict: string; resolution: string; result: unknown;
  failure_context: {reason: string; observations: {code: string; field: string | null}[]} | null;
  events: {kind: string; tool?: string; arguments?: unknown; result?: unknown; raw_arguments?: string}[];
  duration_ms: number;
}
export type Run = {
  id: string; source: string; task: {id: string; request: string; family: string; split: string};
  policy: Policy; attempts: Attempt[]; verdict: string; resolution: string;
  outcome: {success: boolean; critical_error: boolean; checks: Record<string, boolean>} | null;
  before: unknown; after: unknown; total_estimated_usd: number | null; duration_ms: number;
  measurement_complete: boolean; repetition: number;
}
export type Summary = {
  id: string; assigned: number; completed: number; successes: number; success_rate: number;
  total_estimated_usd: number | null; cost_per_success: number | null;
  p95_ms: number | null; median_ms: number | null; escalation_rate: number;
  incorrect_accepted: string[]; critical_errors: number; incomplete_measurements: number;
  savings_vs_ultra: number | null; savings_vs_single: number | null;
  normalization_rate: number; rejection_rate: number; qualifies: boolean;
}
export type Report = {
  schema_version: number; id: string; created_at: string; source: string; split: string;
  manifest_hash: string; provenance: {limitations?: string}; policies: Summary[]; runs: Run[];
  recommendation: {selected: string | null; status: string; reason: string};
}
