import { useMemo } from 'react'
import type { Attempt, Report, Run, ToolEvent } from '../types'
import { attemptCause, attemptCost, causes, money, namesFor, outcomeText, policyName, runtimeText, shortModel, stateDiff, time } from '../lib/evidence'
import { Badge, Icon, PageTitle, Raw } from './Shared'
import s from '../App.module.css'
const readable = (value: unknown) => value == null ? 'None' : typeof value === 'object' ? JSON.stringify(value) : String(value)
const checkNames: Record<string, string> = { no_critical_error: 'No critical error', resolution: 'Appropriate resolution', response: 'Response answers the request', state: 'Final state is correct', terminal: 'Execution reached a final action' }
const codeText: Record<string, string> = { NO_TOOL_CALL: 'The model returned no tool call.', INVALID_JSON: 'The tool arguments could not be parsed as JSON.', REFUSAL_NOT_SUPPORTED: 'The refusal did not match the recorded business rules.', MISSING_REQUIRED_FIELD: 'A required field was missing from the action.', QUERY_REJECTED: 'The read-only query was rejected.', BUSINESS_RULE_VIOLATION: 'The action failed a runtime business-rule check.', INVALID_ARGUMENT_TYPE: 'A tool argument did not match the advertised schema.' }
function toolSummary(event: ToolEvent) {
  const args = event.arguments || {}, result = event.result as Record<string, unknown> | undefined
  switch (event.tool) {
    case 'get_order': return 'Read order ' + readable(args.order_id)
    case 'check_stock': return 'Checked ' + readable(args.sku) + (result?.available != null ? ': ' + readable(result.available) + ' available' : '')
    case 'search_products': return 'Searched the product catalog'
    case 'list_orders': return 'Listed the customer’s orders'
    case 'get_rules': return 'Read the store rules'
    case 'read_only_sql': return 'Queried store data without changing it'
    case 'submit_draft': return 'Submitted an order change for runtime validation'
    case 'submit_answer': return 'Submitted an analysis answer'
    case 'refuse': return 'Proposed refusing the request'
    case 'clarify': return 'Requested clarification'
    default: return event.tool || event.code?.replaceAll('_', ' ').toLowerCase() || event.kind.replaceAll('_', ' ')
  }
}
function ResponseValue({value}: {value: unknown}) {
  if (Array.isArray(value) && value.every(row => row !== null && typeof row === 'object')) {
    const rows = value as Record<string, unknown>[]
    const columns = [...new Set(rows.flatMap(row => Object.keys(row)))].filter(key => rows.some(row => row[key] != null))
    return <div className={s.tableWrap} tabIndex={0} role="region" aria-label="Submitted response values"><table><thead><tr>{columns.map(key => <th key={key}>{key.replaceAll('_', ' ')}</th>)}</tr></thead><tbody>{rows.map((row, i) => <tr key={i}>{columns.map(key => <td key={key}>{readable(row[key])}</td>)}</tr>)}</tbody></table></div>
  }
  return <p>{Array.isArray(value) ? value.map(readable).join(', ') : readable(value)}</p>
}
function AttemptView({attempt, run, index, report}: {attempt: Attempt; run: Run; index: number; report: Report}) {
  const rejected = !['ACCEPT', 'CLARIFY'].includes(attempt.verdict)
  const cause = rejected ? attemptCause(report, run, index) : null
  const observations = attempt.failure_context?.observations || []
  const next = index < run.attempts.length - 1
  return <article className={s.attempt}>
    <div className={`${s.timelineNode} ${rejected ? s.nodeRejected : ''}`} aria-hidden="true">{index + 1}</div>
    <div className={s.attemptHead}><div><span className={s.meta}>Attempt {index + 1}</span><h3>{shortModel(attempt.model)}</h3></div><Badge tone={rejected ? 'warn' : 'good'}>{runtimeText(attempt.verdict)}</Badge></div>
    <div className={s.attemptMetrics}><span><Icon name="clock" size={15} />{time(attempt.duration_ms)}</span><span>{run.source === 'test_fixture' ? 'Cost not measured' : money(attemptCost(attempt)) + ' estimated'}</span><span>{attempt.events.filter(e => e.kind === 'tool').length} tool calls</span></div>
    <ol className={s.toolList}>{attempt.events.map((event, i) => <li key={i}><span className={s.toolDot} aria-hidden="true"/><span>{toolSummary(event)}</span><Raw value={event} label={'Raw ' + (event.tool || event.kind)} /></li>)}</ol>
    {rejected && <div className={s.rejection}><strong>{cause ? causes[cause] : 'Attempt rejected'}</strong>{cause === 'contract' ? <p>The draft repeated a field that matched the original order line. Offline replay verified that this redundant field was rejected by the old contract despite a correct intended change.</p> : observations.length ? observations.map((o, i) => <p key={i}>{codeText[o.code] || o.code.replaceAll('_', ' ').toLowerCase()}{o.field ? ' Field: ' + o.field + '.' : ''}</p>) : <p>The trace does not provide enough detail to infer a more specific cause.</p>}{next && <p className={s.restart}><Icon name="arrow" size={16} /> Clean restart from the original state</p>}</div>}
    <Raw value={{model: attempt.model, failure_context: attempt.failure_context, result: attempt.result, usage: attempt.usage}} label="Full attempt details" />
  </article>
}
export function RunEvidence({run, report}: {run: Run; report: Report}) {
  const changes = useMemo(() => stateDiff(run.before, run.after), [run])
  const last = run.attempts.at(-1)
  const response = last?.result || last?.events.slice().reverse().find(e => ['submit_answer', 'clarify', 'refuse'].includes(e.tool || ''))?.arguments
  return <>
    <section className={s.request}><div className={s.requestTop}><Badge>{run.source === 'live' ? 'Live execution' : run.source === 'test_fixture' ? 'Scripted test fixture' : 'Recorded model execution'}</Badge><span>{policyName(run.policy)} <span className={s.muted}>/ {run.task.family} / repeat {run.repetition + 1}</span></span></div><h2>{run.task.request}</h2><div className={s.runIdentity}><code>{run.id}</code><span>{time(run.duration_ms)} total</span><span>{run.source === 'test_fixture' ? 'Cost not measured' : money(run.total_estimated_usd) + ' estimated'}</span></div></section>
    <div className={s.inspectGrid}><section className={s.panel}><div className={s.sectionHead}><h2>What changed</h2><Badge>{changes.length} field changes</Badge></div>
      {changes.length ? <div className={s.stateChanges}>{changes.map((change, i) => <div className={s.stateChange} key={i}><div><code>{change.id}</code><span>{change.group === 'stock' ? 'Inventory' : change.group === 'lines' ? 'Order line' : change.group} / {change.field.replaceAll('_', ' ')}</span></div><div className={s.changeValues}><span className={s.beforeValue}>{readable(change.before)}</span><Icon name="arrow"/><strong>{readable(change.after)}</strong></div></div>)}</div> : <div className={s.noChange}><Icon name="check" size={22}/><div><h3>No store state changed.</h3><p>{run.resolution === 'answer' ? 'This run returned an analysis answer.' : run.resolution === 'clarification' ? 'This run asked for more information.' : run.resolution === 'refused' ? 'This run refused the requested action.' : 'The recorded before and after states are unchanged.'}</p></div></div>}
      {response && <div className={s.response}><h3>{run.resolution === 'clarification' ? 'Clarification response' : run.resolution === 'answer' ? 'Submitted answer' : 'Final response'}</h3>{Object.entries(response).map(([key, value]) => <div key={key}><span>{key.replaceAll('_', ' ')}</span><ResponseValue value={value}/></div>)}</div>}
      <Raw value={{before: run.before, after: run.after}} label="Original and final state JSON" />
    </section><section className={`${s.panel} ${s.outcomePanel}`}><h2>Independent outcome</h2><Badge tone={run.outcome == null ? 'neutral' : run.outcome.success ? 'good' : 'bad'}>{outcomeText(run)}</Badge><p>Scored after execution. These checks never choose the next model or supply corrections.</p><dl className={s.checks}>{Object.entries(run.outcome?.checks || {}).map(([key, passed]) => <div key={key}><dt>{checkNames[key] || key.replaceAll('_', ' ')}</dt><dd className={passed ? '' : s.failedCheck}>{passed ? 'Pass' : 'Fail'}</dd></div>)}</dl><div className={s.runtimeResult}><span>Final runtime verdict</span><strong>{runtimeText(run.verdict)}</strong><small>Runtime acceptance and independent correctness are separate results.</small></div><p className={s.meta}>Critical accepted error: {run.outcome == null ? 'Not scored' : run.outcome.critical_error ? 'Yes' : 'None observed'}</p><a className={s.textAction} href={'#apply/' + run.policy.id}>Apply this policy <Icon name="arrow" /></a></section></div>
    <section className={`${s.panel} ${s.timelinePanel}`}><div className={s.sectionHead}><div><h2>From attempt to outcome</h2><p>{run.attempts.length > 1 ? 'A rejected attempt is isolated. The next model starts from the original state.' : 'Every tool call and runtime decision stays attached to this execution.'}</p></div><span className={s.meta}>{run.attempts.length} {run.attempts.length === 1 ? 'attempt' : 'attempts'}</span></div><div className={s.timeline}>{run.attempts.map((attempt, i) => <AttemptView key={i} attempt={attempt} run={run} index={i} report={report} />)}</div><Raw value={run} label="Full execution trace JSON" /></section>
  </>
}
export default function Inspect({report, id}: {report: Report; id?: string}) {
  const names = namesFor(report)
  const run = id ? report.runs.find(r => r.id === id) : report.runs.find(r => r.policy.id === report.recommendation.selected && r.attempts.length > 1 && r.outcome?.success) || report.runs[0]
  if (!run) return <section className={s.panel}><h1>{id ? 'Execution not found' : 'No executions yet'}</h1><p>{id ? 'This execution does not belong to the selected report. Select the matching report or return to the comparison.' : 'There are no recorded executions to inspect.'}</p><a href="#compare">Back to comparison</a></section>
  return <><PageTitle title="Execution evidence" description="Follow the decision. Inspect the change. Check the outcome."><label className={s.executionSelect}>Execution<select value={run.id} onChange={e => {window.location.hash = 'inspect/' + e.target.value}}>{report.runs.map(r => <option key={r.id} value={r.id}>{names[r.policy.id]} / {r.task.id} / repeat {r.repetition + 1}</option>)}</select></label></PageTitle><RunEvidence run={run} report={report}/></>
}
