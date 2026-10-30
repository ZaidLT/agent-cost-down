import { useMemo, useState } from 'react'
import type { Report } from '../types'
import { causes, diagnosis, isV4, money, namesFor, pairedCounts, pct, time, verifiedReplay, type Cause } from '../lib/evidence'
import { Badge, Icon, PageTitle } from './Shared'
import s from '../App.module.css'
export default function Compare({report}: {report: Report}) {
  const names = useMemo(() => namesFor(report), [report])
  const data = useMemo(() => diagnosis(report), [report])
  const firstRun = useMemo(() => {const result = new Map<string, string>(); for (const run of report.runs) if (!result.has(run.policy.id)) result.set(run.policy.id, run.id); return result}, [report])
  const [focus, setFocus] = useState<string | null>(null)
  const selected = report.policies.find(p => p.id === report.recommendation.selected)
  const ultra = report.policies.find(p => p.id === 'ultra_only')
  const fixture = report.source === 'test_fixture'
  const validated = !fixture && report.source === 'benchmark' && report.split === 'heldout' && report.recommendation.status === 'validated'
  const headline = validated && selected && selected.savings_vs_ultra != null
  const maxCost = Math.max(...report.policies.map(p => p.total_estimated_usd ?? 0), 0.00001)
  const recovery = report.runs.find(r => r.policy.id === (selected?.id || 'small_ultra') && r.attempts.length > 1 && r.outcome?.success) || report.runs.find(r => r.attempts.length > 1 && r.outcome?.success)
  const failure = report.runs.find(r => r.policy.id === selected?.id && r.verdict === 'ACCEPT' && r.outcome?.success === false) || report.runs.find(r => r.policy.id === selected?.id && r.outcome?.success === false) || report.runs.find(r => r.outcome?.success === false)
  const selectedRuns = report.runs.filter(r => r.policy.id === selected?.id)
  const escalations = selectedRuns.filter(r => r.attempts.length > 1)
  const recoveredEscalations = escalations.filter(r => r.outcome?.success)
  const pairs = selected ? pairedCounts(report, selected.id) : null
  const finalCount = Object.values(data.final).reduce((n, runs) => n + runs.length, 0)
  const originalReplay = verifiedReplay('555720dd79a2c26c')
  return <>
    <PageTitle title="The cost of getting it right." description="Before paying for a bigger model, find out whether the failure comes from the model or your tools." />
    <section className={s.resultBand} aria-label="Recommendation and tradeoffs">
      <div className={s.resultMain}>
        <div className={s.resultLabel}><span>Preselected policy</span><Badge tone={validated ? 'good' : 'warn'}>{fixture ? 'Scripted illustration' : validated ? 'Declared criteria met' : 'Not validated'}</Badge></div>
        <h2>{selected ? names[selected.id] : 'Awaiting model evidence'}</h2>
        {headline ? <p className={s.resultSentence}><strong>{selected.successes}/{selected.assigned} correct</strong>{selected.successes === ultra?.successes ? ', matching Ultra’s observed success count.' : ' observed outcomes.'}</p> : <p>{fixture ? 'Scripted tool calls demonstrate the workflow. They do not measure model quality or savings.' : report.recommendation.reason}</p>}
        {!fixture && selected && <p className={s.recoverySummary}>{escalations.length} escalations, {recoveredEscalations.length} recovered to correct outcomes. {selected.assigned - selected.successes} unsuccessful outcomes.</p>}
        <div className={s.actions}>{recovery && <a className={s.button} href={'#inspect/' + recovery.id}>Inspect a recovery <Icon name="arrow" /></a>}{failure && <a className={s.textAction} href={'#inspect/' + failure.id}>Inspect a remaining failure</a>}<a className={s.textAction} href={'#apply/' + (selected?.id || 'small_ultra')}>Apply the policy</a></div>
      </div>
      <div className={s.resultMetrics}>
        <div><span>Estimated AI cost vs Ultra</span><strong className={headline ? s.cyan : ''}>{headline ? pct(selected.savings_vs_ultra) : fixture ? 'Not measured' : 'Not validated'}</strong><small>{headline ? 'lower on this workload' : 'A savings claim requires a validated measured report'}</small></div>
        <div><span>Median elapsed time</span><strong>{fixture ? 'Not measured' : time(selected?.median_ms)}</strong><small>{fixture ? 'No inference calls' : 'Ultra: ' + time(ultra?.median_ms) + '. Lower cost trades off against speed.'}</small></div>
      </div>
    </section>
    <section className={s.comparison} aria-labelledby="comparison-title">
      <div className={s.sectionHead}><div><h2 id="comparison-title">Five policies. The same workload.</h2><p>{fixture ? 'Labeled scripted examples' : `${report.policies[0]?.assigned ?? 0} executions per policy. Every attempt contributes to cost and latency.`}</p></div><span className={s.meta}>{report.split === 'heldout' ? 'Held-out evaluation' : report.split + ' evaluation'}</span></div>
      <div className={s.chart} role="img" aria-label="Five-policy comparison. Bars show total estimated AI cost on one zero-based scale. Correct outcomes and median elapsed time appear alongside. Exact values are in the accessible table below.">
        <div className={s.chartHeader}><span>Execution policy</span><span>Total estimated AI cost</span><span>Correct</span><span>Median time</span></div>
        {report.policies.map(p => <div key={p.id} className={`${s.chartRow} ${p.id === selected?.id ? s.preselected : ''} ${focus === p.id ? s.focusedRow : ''}`}>
          <div className={s.policyLabel}><strong>{names[p.id]}</strong>{p.id === selected?.id && <span>Preselected</span>}</div>
          <div className={s.barCell}>{fixture || p.total_estimated_usd == null ? <span className={s.unknown}>{fixture ? 'Not measured' : 'Incomplete cost measurement'}</span> : <><div className={s.barTrack}><div className={s.bar} style={{width: `${p.total_estimated_usd / maxCost * 100}%`}} /></div><span className={s.costValue}>{money(p.total_estimated_usd)}</span></>}</div>
          <div className={s.numeric}><strong>{p.successes}<span>/{p.assigned}</span></strong><small>{pct(p.success_rate)}</small></div><div className={s.numeric}>{fixture ? 'Not measured' : time(p.median_ms)}</div>
        </div>)}
        <div className={s.chartScale}><span>Cost scale</span><span>$0</span><span>{money(maxCost)}</span></div>
      </div>
      <details className={s.tableDetails}><summary>View accessible comparison table and measurement details</summary><div className={s.tableWrap} tabIndex={0} role="region" aria-label="Policy comparison table"><table><caption>All figures come from the selected report. Costs are estimates in USD.</caption><thead><tr><th>Policy</th><th>Correct outcomes</th><th>Total cost</th><th>Cost per success</th><th>Median time</th><th>p95 time</th><th>Second attempts</th><th>Incorrect accepted</th><th>Missing measurements</th><th>Evidence</th></tr></thead><tbody>{report.policies.map(p => <tr key={p.id}><th scope="row">{names[p.id]}</th><td>{p.successes}/{p.assigned}</td><td>{fixture ? 'Not measured' : money(p.total_estimated_usd)}</td><td>{fixture ? 'Not measured' : money(p.cost_per_success)}</td><td>{fixture ? 'Not measured' : time(p.median_ms)}</td><td>{fixture ? 'Not measured' : time(p.p95_ms)}</td><td>{pct(p.escalation_rate)}</td><td>{p.incorrect_accepted.length}</td><td>{p.incomplete_measurements}</td><td>{firstRun.has(p.id) ? <a href={'#inspect/' + firstRun.get(p.id)}>Inspect {names[p.id]}</a> : 'No recorded execution'}</td></tr>)}</tbody></table></div></details>
      {!fixture && <div className={s.alternatives}><span>Measured alternatives</span>{[['small_ultra', 'Lower cost, matching Ultra’s observed correctness'], ['ultra_only', 'Faster'], ['small_retry', 'Lower budget']].filter(([id]) => report.policies.some(p => p.id === id)).map(([id, label]) => { const p = report.policies.find(p => p.id === id)!; return <button className={s.alternative} key={id} aria-pressed={focus === id} onClick={() => setFocus(focus === id ? null : id)}><strong>{names[id]}</strong><span>{id === 'small_ultra' && p.successes !== ultra?.successes ? 'Escalation policy' : label}{id !== 'small_ultra' ? ' · ' + pct(p.success_rate) + ' observed correctness' : ''}</span></button> })}<small>Highlighting an alternative does not change the preselected recommendation.</small></div>}
    </section>
    {!fixture && <section className={s.story} aria-label="The experiment story">
      <article><span className={s.storyNumber}>1</span><div><h3>V3 exposed a failure.</h3><p>The cheap policy selected on development data failed the original evaluation.</p></div></article>
      <article><span className={s.storyNumber}>2</span><div><h3>The tool contract was part of it.</h3><p>Offline replay traced {originalReplay.final_failures.length} of {originalReplay.total_final_failures} final v3 failures to inconsistent redundant-field checks. These are diagnostic corrections, not new model successes.</p></div></article>
      <article><span className={s.storyNumber}>3</span><div><h3>{isV4(report) ? 'V4 tested the amendment.' : 'An amended rerun followed.'}</h3><p>{isV4(report) && validated ? 'The preselected policy met its declared criteria in a controlled rerun of the inspected suite.' : 'The original evidence stays unchanged. Select a published v4 report to inspect the controlled rerun.'}</p></div></article>
    </section>}
    <section className={s.panel} aria-labelledby="diagnosis-title"><div className={s.sectionHead}><div><h2 id="diagnosis-title">Why did runs fail?</h2><p>Final failures are counted once, by their terminal evidence. Recovered attempts are separate.</p></div><Badge tone={finalCount ? 'warn' : 'neutral'}>{finalCount} final failures</Badge></div>
      <div className={s.diagnosisGrid}><div>{(Object.entries(causes) as [Cause, string][]).map(([cause, label]) => <details className={s.cause} key={cause}><summary><span>{label}</span><span className={s.causeCount}>{data.final[cause].length}</span></summary><div className={s.causeBody}>{data.final[cause].length ? report.policies.map(p => {const runs = data.final[cause].filter(r => r.policy.id === p.id); return runs.length ? <div key={p.id}><h4>{names[p.id]} <span>({runs.length})</span></h4><div className={s.runLinks}>{runs.map(r => <a key={r.id} href={'#inspect/' + r.id}>{r.task.id}, repeat {r.repetition + 1}<code>{r.id}</code></a>)}</div></div> : null}) : <p>No final failures in this category.</p>}</div></details>)}</div>
      <aside className={s.diagnosisAside}><h3>Rejected does not mean wrong forever.</h3><p>A runtime check can reject an attempt, trigger a clean restart, and still lead to a correct final outcome.</p><strong className={s.asideNumber}>{data.recovered.length}</strong><p>failed attempts recovered to correct outcomes across all policies.</p><details><summary>Inspect recovered attempts</summary><div className={s.runLinks}>{data.recovered.map(({run, attempt, cause}) => <a href={'#inspect/' + run.id} key={run.id + attempt}>{names[run.policy.id]}, attempt {attempt + 1}<span>{causes[cause]}</span><code>{run.id}</code></a>)}</div></details><p className={s.meta}>A generic business-rule rejection is never sufficient to prove the verified contract defect.</p></aside></div>
    </section>
    {!fixture && <section className={s.method}><div><h2>What the evidence can tell us</h2><p>{report.provenance.limitations || 'A small synthetic workload. Outcomes and costs do not guarantee production performance.'}</p><p>{new Set(report.runs.map(r => r.task.id)).size} distinct tasks{report.split === 'heldout' ? ', repeated three times per policy, covering seven underlying scenarios.' : ' in this development report.'} Repetitions and numeric variants are not independent real-world task types.</p>{selected && <p>Preselected policy: {selected.critical_errors} observed critical errors. {selected.incorrect_accepted_mutations?.length ?? 'Unknown'} incorrect accepted mutations. {selected.incorrect_accepted.length} incorrect accepted outcomes.</p>}<code>Report {report.id}</code></div>{pairs && <div className={s.paired}><h3>{names[selected!.id]} paired with Ultra</h3><dl><div><dt>Both succeeded</dt><dd>{pairs.both}</dd></div><div><dt>Only {names[selected!.id]} succeeded</dt><dd>{pairs.policy}</dd></div><div><dt>Only Ultra succeeded</dt><dd>{pairs.ultra}</dd></div><div><dt>Neither succeeded</dt><dd>{pairs.neither}</dd></div></dl><p>Equal observed success counts do not establish statistical equivalence.</p></div>}</section>}
  </>
}
