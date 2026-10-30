import { useEffect, useState, useSyncExternalStore } from 'react'
import type { Report, ReportEntry } from './types'
import { disclosure, isV4 } from './lib/evidence'
import { useLiveRun } from './lib/useLiveRun'
import Compare from './components/Compare'
import Inspect from './components/Inspect'
import Apply from './components/Apply'
import { Icon, Mark } from './components/Shared'
import s from './App.module.css'
const subscribe = (cb: () => void) => { window.addEventListener('hashchange', cb);window.addEventListener('popstate', cb);return () => {window.removeEventListener('hashchange', cb);window.removeEventListener('popstate', cb)} }
const snapshot = () => window.location.search + '|' + window.location.hash
const filePattern = /^[a-zA-Z0-9_-]+\.json$/
export default function App() {
  const location = useSyncExternalStore(subscribe, snapshot)
  const [route, id] = (window.location.hash.slice(1) || 'compare').split('/')
  const page = ['compare', 'inspect', 'apply'].includes(route) ? route : 'compare'
  const [index, setIndex] = useState<{active: string; reports: ReportEntry[]} | null>(null)
  const [report, setReport] = useState<Report | null>(null)
  const [error, setError] = useState(false)
  const [retry, setRetry] = useState(0)
  const requested = new URLSearchParams(location.split('|')[0]).get('report')
  const file = index?.reports.find(r => r.file === requested)?.file || index?.active
  const live = useLiveRun(import.meta.env.VITE_API_URL, page === 'apply')
  useEffect(() => {
    const controller = new AbortController();setError(false)
    fetch('/reports/index.json', {signal: controller.signal}).then(r => {if (!r.ok) throw new Error();return r.json()}).then(value => {
      if (typeof value.active !== 'string' || !filePattern.test(value.active)) throw new Error()
      const entries = (Array.isArray(value.reports) ? value.reports : []).filter((e: ReportEntry) => typeof e.file === 'string' && filePattern.test(e.file) && typeof e.label === 'string')
      setIndex({active: value.active, reports: entries.length ? entries : [{file: value.active, label: 'Active report'}]})
    }).catch(e => {if (e.name !== 'AbortError') setError(true)})
    return () => controller.abort()
  }, [retry])
  useEffect(() => {
    if (!file) return
    const controller = new AbortController();setReport(null);setError(false)
    fetch('/reports/' + file, {signal: controller.signal}).then(r => {if (!r.ok) throw new Error();return r.json()}).then(value => {
      if (value.schema_version !== 1 || !Array.isArray(value.runs) || !Array.isArray(value.policies) || !value.provenance || !value.recommendation) throw new Error()
      setReport(value)
    }).catch(e => {if (e.name !== 'AbortError') setError(true)})
    return () => controller.abort()
  }, [file, retry])
  function changeReport(next: string) {const url = new URL(window.location.href);url.searchParams.set('report', next);url.hash = 'compare';window.history.pushState(null, '', url);window.dispatchEvent(new PopStateEvent('popstate'))}
  return <><a className={s.skip} href="#main-content" onClick={e => {e.preventDefault();document.getElementById('main-content')?.focus()}}>Skip to content</a>
    <header className={s.header}><div className={s.headerInner}><a className={s.brand} href="#compare"><Mark/><span>Agent Cost Down</span></a><nav aria-label="Main navigation">{['compare', 'inspect', 'apply'].map((p, i) => <a key={p} href={'#' + p} aria-current={page === p ? 'page' : undefined}><span className={s.navIndex}>{i + 1}</span>{p[0].toUpperCase() + p.slice(1)}</a>)}</nav><div className={s.headerUtilities}>{index && <label className={s.reportSelect}><span className={s.srOnly}>Experiment version</span><select aria-label="Experiment version" value={file} onChange={e => changeReport(e.target.value)}>{index.reports.map(r => <option key={r.file} value={r.file}>{r.label}</option>)}</select></label>}<a className={s.repo} href="https://github.com/ZaidLT/agent-cost-down" aria-label="Source code">Source <Icon name="external" size={14}/></a></div></div></header>
    {report && (isV4(report) || report.provenance.evaluation_disclosure) && <aside className={s.disclosure}><div><span className={s.disclosureMark} aria-hidden="true">i</span><p>{isV4(report) ? disclosure : report.provenance.evaluation_disclosure}</p></div></aside>}
    {report?.source === 'test_fixture' && <aside className={s.fixtureBanner}>Scripted illustration. No real model results or cost savings have been measured.</aside>}
    <main id="main-content" tabIndex={-1} className={s.main}>{error ? <section className={s.panel}><h1>The report could not be loaded.</h1><p>The saved evidence is unavailable. Reload to try again.</p><button onClick={() => setRetry(n => n + 1)}>Reload report</button></section> : !report ? <section className={s.loading} role="status"><h1>Loading the saved report…</h1><div/><div/><div/></section> : page === 'inspect' ? <Inspect report={report} id={id}/> : page === 'apply' ? <Apply key={report.id + '/' + id} report={report} id={id} live={live}/> : <Compare key={report.id} report={report}/>}</main>
    <footer className={s.footer}><div><span>Agent Cost Down</span><span>Built with NVIDIA Nemotron on Nebius Token Factory.</span></div><div><span>Synthetic tasks. Explicit failures. Runnable policies.</span><a href="https://github.com/ZaidLT/agent-cost-down#quickstart">Reproduce locally <Icon name="external" size={14}/></a></div></footer>
  </>
}
