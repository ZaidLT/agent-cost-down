import { useEffect, useState, useSyncExternalStore } from 'react'
import type { Report, Run, Policy } from './types'
import s from './App.module.css'

const names: Record<string, string> = {
  small_only: 'Small only', super_only: 'Super only', ultra_only: 'Ultra only',
  small_retry: 'Small + retry', small_ultra: 'Small + Ultra',
}
const dollars = (n: number | null) => n === null ? 'Incomplete' : '$' + n.toFixed(5)
const percent = (n: number | null) => n === null ? 'Unavailable' : (n * 100).toFixed(1) + '%'
const seconds = (n: number | null) => n === null ? 'Unavailable' : (n / 1000).toFixed(1) + 's'
const subscribe = (cb: () => void) => { window.addEventListener('hashchange', cb); return () => window.removeEventListener('hashchange', cb) }
const snapshot = () => window.location.hash.slice(1) || 'compare'
function Json({value}: {value: unknown}) { return <pre className={s.json}>{JSON.stringify(value, null, 2)}</pre> }
function Badge({children, bad = false}: {children: React.ReactNode; bad?: boolean}) {
  return <span className={bad ? s.badgeBad : s.badge}>{children}</span>
}

function Compare({report}: {report: Report}) {
  const fixture = report.source === 'test_fixture'
  const measured = report.policies.filter(p => p.total_estimated_usd !== null)
  const maxCost = Math.max(...measured.map(p => p.total_estimated_usd || 0), 0.00001)
  return <>
    <div className={s.intro}>
      <div><h1>Compare the cost.<br />Inspect the outcome.</h1><p>Choose an execution policy from evidence, then run the configuration you export.</p></div>
      <aside className={s.verdict}><span>Recommendation</span><h2>{fixture ? 'Awaiting model evidence' : report.recommendation.status === 'validated' ? names[report.recommendation.selected!] : 'Not validated'}</h2>
        <p>{fixture ? 'This interactive example uses scripted tool calls. It demonstrates the workflow without claiming model quality or savings.' : report.recommendation.reason}</p>
        <a href={'#inspect/' + report.runs[0]?.id}>Inspect an execution</a>
      </aside>
    </div>
    <section className={s.panel} aria-labelledby="comparison-title">
      <div className={s.sectionHead}><h2 id="comparison-title">Five policies, one workload</h2><span>{fixture ? 'Scripted illustration' : report.split + ' evaluation'}</span></div>
      <div className={s.tableWrap}><table><caption className={s.srOnly}>Policy outcomes and estimated cost on identical assigned tasks</caption>
        <thead><tr><th>Policy</th><th>{fixture ? 'Scripted checks' : 'Successful runs'}</th><th>Estimated cost</th><th>p95 time</th><th>Incorrect accepted</th><th>Evidence</th></tr></thead>
        <tbody>{report.policies.map(p => <tr key={p.id}>
          <th scope="row">{names[p.id]}{p.id === report.recommendation.selected && <Badge>Preselected</Badge>}</th>
          <td>{p.successes} / {p.assigned}</td><td>{fixture ? 'Not measured' : dollars(p.total_estimated_usd)}</td>
          <td>{fixture ? 'Not measured' : seconds(p.p95_ms)}</td><td>{p.incorrect_accepted.length}</td>
          <td>{report.runs.find(r => r.policy.id === p.id) ? <a href={'#inspect/' + report.runs.find(r => r.policy.id === p.id)!.id}>Inspect {names[p.id]}</a> : 'No completed run'}</td>
        </tr>)}</tbody></table></div>
    </section>
    <div className={s.twoColumns}>
      <section className={s.panel}><h2>Cost and successful outcomes</h2>
        {fixture ? <div className={s.emptyPlot}><svg viewBox="0 0 420 160" aria-hidden="true"><path d="M30 10V140H400" fill="none" stroke="currentColor" /><path d="M30 70H400M210 10V140" fill="none" stroke="currentColor" strokeDasharray="4 6" /></svg><p>The plot will appear when a measured report is published.</p></div> :
          <svg className={s.plot} viewBox="0 0 560 300" role="img" aria-label="Estimated cost on the horizontal axis, successful runs on the vertical axis. Exact values are in the table above.">
            <path d="M60 20V250H525" fill="none" stroke="#64748b" />
            <text x="60" y="280">Lower estimated cost</text><text x="8" y="17">100%</text><text x="22" y="250">0%</text>
            {measured.map((p, i) => <g key={p.id}><circle cx={60 + (p.total_estimated_usd || 0) / maxCost * 390} cy={250 - p.success_rate * 220} r={6} fill={p.qualifies ? '#1d4ed8' : '#64748b'} />
              <text x={70 + (p.total_estimated_usd || 0) / maxCost * 390} y={245 - p.success_rate * 220 - i * 4} fontSize="12">{names[p.id]}</text></g>)}
          </svg>}
      </section>
      <section className={s.panel}><h2>What this proves</h2><p>The runtime checks whether an action is allowed. A separate evaluator checks whether it answers the request. Both results stay visible.</p>
        <dl className={s.facts}><dt>Report</dt><dd>{report.id}</dd><dt>Source</dt><dd>{fixture ? 'Scripted test fixture' : 'Recorded model executions'}</dd><dt>Scope</dt><dd>{report.provenance.limitations || 'Synthetic store tasks, with an independent evaluator.'}</dd></dl>
        <a href="/reports/illustration.json" download hidden={!fixture}>Download the labeled illustration</a>
      </section>
    </div>
    {!fixture && <section className={s.panel}><h2>Measurement details</h2><div className={s.tableWrap}><table><thead><tr><th>Policy</th><th>Cost / success</th><th>Saving vs Ultra</th><th>Saving vs single</th><th>Escalation</th><th>Normalization</th><th>Incomplete</th></tr></thead>
      <tbody>{report.policies.map(p => <tr key={p.id}><th>{names[p.id]}</th><td>{dollars(p.cost_per_success)}</td><td>{percent(p.savings_vs_ultra)}</td><td>{percent(p.savings_vs_single)}</td><td>{percent(p.escalation_rate)}</td><td>{percent(p.normalization_rate)}</td><td>{p.incomplete_measurements}</td></tr>)}</tbody></table></div></section>}
  </>
}

function Inspect({report, id}: {report: Report; id?: string}) {
  const run = report.runs.find(r => r.id === id) || report.runs[0]
  if (!run) return <div className={s.panel}><h1>No executions yet</h1><p>Publish a report after completing the planned evaluation.</p></div>
  return <>
    <div className={s.sectionHead}><div><a href="#compare">Back to comparison</a><h1>Inspect an execution</h1></div>
      <label>Execution<select value={run.id} onChange={e => { window.location.hash = 'inspect/' + e.target.value }}>
        {report.runs.map(r => <option key={r.id} value={r.id}>{names[r.policy.id]} / {r.task.id} / repeat {r.repetition + 1}</option>)}</select></label>
    </div>
    <section className={s.request}><Badge>{run.source === 'test_fixture' ? 'Scripted test fixture' : 'Recorded model execution'}</Badge><h2>{run.task.request}</h2>
      <p>{names[run.policy.id]} · {run.task.family} · {run.task.split}</p></section>
    <div className={s.twoColumns}>
      <section className={s.panel}><h2>Execution and runtime checks</h2>
        {run.attempts.map((a, i) => <article className={s.attempt} key={i}>
          <div className={s.sectionHead}><h3>Attempt {i + 1}: {a.model}</h3><Badge bad={a.verdict !== 'ACCEPT'}>{a.verdict}</Badge></div>
          {a.failure_context && <div className={s.failure}><strong>Restart from the original state</strong><p>{a.failure_context.reason.replaceAll('_', ' ')}</p><Json value={a.failure_context} /></div>}
          {a.events.map((event, j) => <details key={j}><summary>{event.tool || event.kind}</summary><Json value={event} /></details>)}
        </article>)}
        <p>Final runtime result: <strong>{run.verdict}</strong>, {run.resolution}.</p>
      </section>
      <section className={s.panel}><h2>Independent outcome</h2><Badge bad={!run.outcome?.success}>{run.outcome?.success ? 'Correct outcome' : 'Incorrect or unscored'}</Badge>
        <p>Scored after execution. These checks never select the next model or send it corrections.</p>
        <dl className={s.facts}>{Object.entries(run.outcome?.checks || {}).map(([key, value]) => <div key={key}><dt>{key.replaceAll('_', ' ')}</dt><dd>{value ? 'Pass' : 'Fail'}</dd></div>)}</dl>
        <p>Critical accepted error: {run.outcome?.critical_error ? 'Yes' : 'No'}</p>
        <p>Estimated inference cost: {run.source === 'test_fixture' ? 'Not measured' : dollars(run.total_estimated_usd)}</p>
        <a className={s.button} href={'#apply/' + run.policy.id}>Apply this policy</a>
      </section>
    </div>
    <section className={s.panel}><h2>Original and final state</h2><div className={s.twoColumns}><details><summary>Before execution</summary><Json value={run.before} /></details><details><summary>After execution</summary><Json value={run.after} /></details></div></section>
  </>
}

function Apply({report, id}: {report: Report; id?: string}) {
  const [selected, setSelected] = useState(id || report.recommendation.selected || 'small_ultra')
  const [judge, setJudge] = useState('')
  const [task, setTask] = useState('resolution-development-1')
  const [status, setStatus] = useState('')
  const [busy, setBusy] = useState(false)
  const [liveResult, setLiveResult] = useState<Run | null>(null)
  const [failed, setFailed] = useState(false)
  const [currentRun, setCurrentRun] = useState<string | null>(null)
  const [catalog, setCatalog] = useState<{tasks: string[]; available: boolean} | null>(null)
  const [copied, setCopied] = useState(false)
  const api = import.meta.env.VITE_API_URL as string | undefined
  const config = report.runs.find(r => r.policy.id === selected)?.policy
  const fixture = report.source === 'test_fixture'
  useEffect(() => {
    if (!api) return
    const controller = new AbortController()
    fetch(api + '/v1/catalog', {signal: controller.signal}).then(r => r.ok ? r.json() : Promise.reject()).then(setCatalog).catch(() => {})
    return () => controller.abort()
  }, [api])
  useEffect(() => {
    if (!currentRun || !api) return
    let cancelled = false
    let timer: ReturnType<typeof setTimeout>
    let polls = 0
    const poll = async () => {
      try {
        const response = await fetch(api + '/v1/runs/' + currentRun, {signal: AbortSignal.timeout(20000)})
        if (!response.ok) throw new Error('Job status is unavailable. Keep the run ID and check again; do not submit a replacement.')
        const result = await response.json()
        if (cancelled) return
        setStatus('Live run ' + currentRun + ': ' + result.status)
        if (result.status === 'complete') { setLiveResult(result.result); setBusy(false); setCurrentRun(null); return }
        if (['failed', 'interrupted'].includes(result.status)) throw new Error(result.error || 'Execution failed')
        if (++polls > 170) throw new Error('The wait limit was reached. Keep this run ID; its outcome may still be pending.')
        timer = setTimeout(poll, 4000)
      } catch (error) {
        if (!cancelled) { setStatus(String(error)); setFailed(true); setBusy(false); setCurrentRun(null) }
      }
    }
    void poll()
    return () => { cancelled = true; clearTimeout(timer) }
  }, [currentRun, api])
  function download() {
    if (!config) return
    const blob = new Blob([JSON.stringify({...config, supporting_report: report.id}, null, 2)], {type: 'application/json'})
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a'); a.href = url; a.download = 'policy.json'; a.click()
    setTimeout(() => URL.revokeObjectURL(url), 1000)
  }
  async function start() {
    if (!api || busy) return
    setBusy(true); setFailed(false); setLiveResult(null)
    setStatus('Connecting to the live service. A sleeping free service can take a minute to wake.')
    const key = crypto.randomUUID()
    try {
      const response = await fetch(api + '/v1/runs', {method: 'POST', signal: AbortSignal.timeout(90000),
        headers: {'Content-Type': 'application/json', 'Idempotency-Key': key, ...(judge ? {'X-Judge-Code': judge} : {})},
        body: JSON.stringify({task_id: task, policy_id: selected})})
      const payload = await response.json()
      if (!response.ok) throw new Error(payload.detail || 'Live service unavailable')
      setStatus('Live run: ' + payload.id); setCurrentRun(payload.id)
    } catch (error) {
      setStatus(String(error) + ' Request key: ' + key + '. A lost response does not mean a call was free.')
      setFailed(true); setBusy(false)
    }
  }
  const command = 'uv run acd run --config policy.json --task resolution-development-1'
  return <>
    <h1>Run the policy you inspected.</h1><p className={s.lead}>The exported file controls the same execution engine used in the comparison.</p>
    <div className={s.twoColumns}>
      <section className={s.panel}><h2>Export a configuration</h2><label>Policy<select value={selected} onChange={e => setSelected(e.target.value)}>{Object.entries(names).map(([key, name]) => <option key={key} value={key}>{name}</option>)}</select></label>
        {fixture && <p className={s.notice}>This export uses test model identifiers. It demonstrates the contract and cannot call Token Factory. A measured report will contain verified provider identifiers.</p>}
        {config ? <><Json value={{...config, supporting_report: report.id} as Policy} /><button onClick={download}>Download policy.json</button></> : <p>No configuration is available for this policy yet.</p>}
        <h3>Apply locally</h3><pre className={s.json}>{command}</pre><button className={s.secondary} onClick={async () => { try {await navigator.clipboard.writeText(command); setCopied(true)} catch { setCopied(false) } }}>{copied ? 'Command copied' : 'Copy command'}</button>
      </section>
      <section className={s.panel}><h2>Try a fresh sample</h2><p>A live sample has a fixed request and a bounded budget. Public access allows two submissions per hour.</p>
        <label>Task<select value={task} onChange={e => setTask(e.target.value)}>{(catalog?.tasks || ['resolution-development-1']).map(t => <option key={t} value={t}>{t}</option>)}</select></label>
        <label>Judge access code (optional)<input type="password" autoComplete="off" value={judge} onChange={e => setJudge(e.target.value)} /></label>
        <p className={s.hint}>Use the code from the testing instructions. It stays in this page’s memory.</p>
        <button disabled={busy || !api || !catalog?.available} onClick={start}>{busy ? 'Run in progress' : 'Start live sample'}</button>
        {!api && <p className={s.notice}>Live execution is not connected. The report explorer works independently.</p>}
        <p role="status" aria-live="polite">{status}</p>
        {failed && <div className={s.failure}><p>The live attempt remains failed or pending. It has not been replaced with a cached success.</p>
          <a href={'#inspect/' + report.runs[0]?.id}>{fixture ? 'Open the scripted illustration' : 'Open a genuine recorded execution'}</a></div>}
        {liveResult && <><Badge>Live execution</Badge><p>Runtime: {liveResult.verdict}. Independent result: {liveResult.outcome?.success ? 'Correct' : 'Incorrect or unscored'}.</p><details><summary>Inspect live trace</summary><Json value={liveResult} /></details></>}
      </section>
    </div>
  </>
}

export default function App() {
  const route = useSyncExternalStore(subscribe, snapshot)
  const [report, setReport] = useState<Report | null>(null)
  const [error, setError] = useState(false)
  useEffect(() => {
    const controller = new AbortController()
    fetch('/reports/index.json', {signal: controller.signal}).then(r => {if (!r.ok) throw new Error(); return r.json()})
      .then(index => fetch('/reports/' + index.active, {signal: controller.signal}))
      .then(r => {if (!r.ok) throw new Error(); return r.json()})
      .then(value => {if (value.schema_version !== 1 || !Array.isArray(value.runs)) throw new Error(); setReport(value)})
      .catch(e => {if (e.name !== 'AbortError') setError(true)})
    return () => controller.abort()
  }, [])
  const [page, id] = route.split('/')
  return <><a className={s.skip} href="#main-content">Skip to content</a>
    <header className={s.header}><a className={s.brand} href="#compare"><svg viewBox="0 0 30 30" aria-hidden="true"><path d="M3 7h10v6H3zm0 10h10v6H3zm14-5h10v6H17z" fill="currentColor"/><path d="M13 10h2v5h2m-4 5h2v-5" fill="none" stroke="currentColor" strokeWidth="2"/></svg>Agent Cost Down</a>
      <nav aria-label="Main navigation">{['compare', 'inspect', 'apply'].map(p => <a key={p} href={'#' + p} aria-current={page === p ? 'page' : undefined}>{p[0].toUpperCase() + p.slice(1)}</a>)}</nav>
      <a className={s.repo} href="https://github.com/ZaidLT/agent-cost-down">Source code</a></header>
    {report?.source === 'test_fixture' && <div className={s.banner}>Scripted illustration. No real model results or cost savings have been measured.</div>}
    <main id="main-content" className={s.main}>
      {error ? <section className={s.panel}><h1>The report could not be loaded.</h1><p>Refresh to retry. No live inference was started.</p><button onClick={() => window.location.reload()}>Reload report</button></section> :
       !report ? <p role="status">Loading the saved report...</p> :
       page === 'inspect' ? <Inspect report={report} id={id} /> : page === 'apply' ? <Apply key={id} report={report} id={id} /> : <Compare report={report} />}
    </main><footer className={s.footer}>Agent Cost Down · Synthetic tasks. Explicit failures. Runnable policies.<a href="https://github.com/ZaidLT/agent-cost-down#quickstart">Reproduce locally</a></footer>
  </>
}
