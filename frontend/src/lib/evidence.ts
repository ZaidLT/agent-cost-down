import type { Attempt, Policy, Report, Run, StoreState } from '../types'
import replay from '../data/v3-replay.json' with {type: 'json'}

export const policyIds = ['small_only', 'super_only', 'ultra_only', 'small_retry', 'small_ultra'] as const
export const disclosure = 'Controlled rerun on the same evaluation suite. These tasks and their v3 results were inspected before the v4 amendment. This is not fresh independent validation.'
export const isV4 = (r: Report) => String(r.provenance.protocol_version) === '4' || ['135c81cc2a5991c2', '04f6d572b16fa8a5'].includes(r.id) || Boolean(r.provenance.evaluation_disclosure?.includes('v4 amendment'))
export const money = (n: number | null | undefined, digits = 5) => n == null || !Number.isFinite(n) ? 'Unknown' : '$' + n.toFixed(digits)
export const pct = (n: number | null | undefined) => n == null || !Number.isFinite(n) ? 'Unavailable' : (n * 100).toFixed(1) + '%'
export const time = (n: number | null | undefined) => n == null || !Number.isFinite(n) ? 'Unknown' : (n / 1000).toFixed(2) + ' s'
export const shortModel = (id: string) => /lightning/i.test(id) ? 'Lightning' : /nano|small/i.test(id) ? 'Nano' : /super/i.test(id) ? 'Super' : /ultra/i.test(id) ? 'Ultra' : id
export function policyName(policy: Policy) {
  const models = policy.models.map(m => shortModel(m.id))
  return policy.id === 'small_retry' ? models[0] + ' + retry' : models.join(' → ')
}
export function namesFor(report: Report) {
  return Object.fromEntries(report.policies.map(p => {
    const config = report.runs.find(r => r.policy.id === p.id)?.policy
    return [p.id, config ? policyName(config) : p.id.replaceAll('_', ' ')]
  }))
}
export function stable(value: unknown): string {
  if (Array.isArray(value)) return '[' + value.map(stable).join(',') + ']'
  if (value !== null && typeof value === 'object') return '{' + Object.keys(value).sort().map(k => JSON.stringify(k) + ':' + stable((value as Record<string, unknown>)[k])).join(',') + '}'
  return JSON.stringify(value) ?? 'null'
}
export const exportedPolicy = (config: Policy, reportId: string) => ({ ...config, supporting_report: reportId })
export const outcomeText = (run: Run) => run.outcome == null ? 'Not independently scored' : run.outcome.success ? 'Correct outcome' : 'Incorrect outcome'
export const runtimeText = (verdict: string) => ({ ACCEPT: 'Accepted by runtime', CLARIFY: 'Clarification requested', RETRY: 'Rejected by runtime', UNRESOLVED: 'Unresolved', INTERRUPTED: 'Interrupted' }[verdict] || verdict.replaceAll('_', ' ').toLowerCase())
export const attemptCost = (a: Attempt) => !a.usage?.length || a.usage.some(u => u.estimated_usd == null) ? null : a.usage.reduce((sum, u) => sum + u.estimated_usd!, 0)

export const causes = {
  contract: 'Verified redundant-field contract rejection', runtime: 'Other runtime or business-rule rejection', missing: 'Missing tool call', json: 'Malformed JSON', schema: 'Tool-argument schema failure', clarification: 'Clarification-scoring failure', incorrect: 'Incorrect accepted outcome', provider: 'Provider failure', deadline: 'Deadline interruption', unclassified: 'Unclassified failure',
} as const
export type Cause = keyof typeof causes
const replayReports = replay.reports as Record<string, { attempts: string[]; final_failures: string[]; total_final_failures: number }>
export function attemptCause(report: Report, run: Run, index: number): Cause {
  const attempt = run.attempts[index]
  if (!attempt) return 'unclassified'
  const codes = [...attempt.events.map(e => e.code || ''), ...(attempt.failure_context?.observations.map(o => o.code) || [])]
  const reason = attempt.failure_context?.reason || ''
  // Recorded events take precedence over the inaccurate legacy parse label.
  if (codes.includes('NO_TOOL_CALL')) return 'missing'
  if (replayReports[report.id]?.attempts.includes(run.id + ':' + index)) return 'contract'
  if (codes.some(c => /DEADLINE|TIMEOUT|INTERRUPT/.test(c)) || /deadline|interrupted/.test(reason) || attempt.events.some(e => /deadline|interrupt/.test(e.kind))) return 'deadline'
  if (attempt.events.some(e => e.kind === 'provider_failure') || /provider/.test(reason)) return 'provider'
  if (reason === 'tool_schema_failed' || codes.some(c => /INVALID_ARGUMENT_TYPE|SCHEMA/.test(c))) return 'schema'
  if (codes.includes('INVALID_JSON') || reason === 'parse_failed') return 'json'
  if (reason === 'runtime_validation_failed' || codes.includes('BUSINESS_RULE_VIOLATION')) return 'runtime'
  return 'unclassified'
}
export function finalCause(report: Report, run: Run): Cause | null {
  if (run.outcome?.success) return null
  if (run.outcome && run.verdict === 'CLARIFY' && !run.outcome.checks.response) return 'clarification'
  if (run.outcome && run.verdict === 'ACCEPT') return 'incorrect'
  if (/INTERRUPT|DEADLINE/.test(run.verdict)) return 'deadline'
  return attemptCause(report, run, run.attempts.length - 1)
}
export function diagnosis(report: Report) {
  const final = Object.fromEntries(Object.keys(causes).map(k => [k, [] as Run[]])) as Record<Cause, Run[]>
  const recovered: { run: Run; attempt: number; cause: Cause }[] = []
  for (const run of report.runs) {
    const cause = finalCause(report, run)
    if (cause) final[cause].push(run)
    if (run.outcome?.success) run.attempts.slice(0, -1).forEach((a, i) => {
      if (a.verdict !== 'ACCEPT' && a.verdict !== 'CLARIFY') recovered.push({run, attempt: i, cause: attemptCause(report, run, i)})
    })
  }
  return {final, recovered}
}
export function pairedCounts(report: Report, policy: string) {
  const pairs = report.provenance.paired?.filter(p => p.policy === policy)
  if (!pairs?.length) return null
  return pairs.reduce((c, p) => { c[p.success ? p.ultra_success ? 'both' : 'policy' : p.ultra_success ? 'ultra' : 'neither']++; return c }, {both: 0, policy: 0, ultra: 0, neither: 0})
}
export type StateChange = { group: string; id: string; field: string; before: unknown; after: unknown }
export function stateDiff(before: StoreState, after: StoreState): StateChange[] {
  const changes: StateChange[] = []
  for (const [group, key] of [['lines', 'id'], ['orders', 'id'], ['stock', 'sku'], ['products', 'sku']] as const) {
    const original = new Map((before[group] || []).map(row => [String(row[key]), row]))
    const final = new Map((after[group] || []).map(row => [String(row[key]), row]))
    for (const id of new Set([...original.keys(), ...final.keys()])) {
      const a = original.get(id), b = final.get(id)
      if (!a || !b) { changes.push({group, id, field: a ? 'Removed' : 'Added', before: a ?? null, after: b ?? null}); continue }
      for (const field of new Set([...Object.keys(a), ...Object.keys(b)])) if (stable(a[field]) !== stable(b[field])) changes.push({group, id, field, before: a[field], after: b[field]})
    }
  }
  return changes
}
export function verifiedReplay(reportId: string) { return replayReports[reportId] }
