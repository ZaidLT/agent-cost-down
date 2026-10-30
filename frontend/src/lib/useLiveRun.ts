import { useEffect, useRef, useState } from 'react'
import type { Catalog, Run } from '../types'
export type Submission = { task_id: string; policy_id: string }
type LiveState = { phase: 'idle' | 'submitting' | 'queued' | 'complete' | 'failed' | 'uncertain' | 'paused'; key?: string; request?: Submission; runId?: string; result?: Run; message: string }
export function useLiveRun(api: string | undefined, enabled: boolean) {
  const [catalog, setCatalog] = useState<Catalog | null>(null)
  const [connection, setConnection] = useState(api ? 'Not checked' : 'Not connected')
  const [judge, setJudge] = useState('')
  const [state, setState] = useState<LiveState>({phase: 'idle', message: ''})
  const [check, setCheck] = useState(0)
  const [pollVersion, setPollVersion] = useState(0)
  const locked = useRef(false)
  const submissionJudge = useRef('')
  const base = api?.replace(/\/$/, '')
  useEffect(() => {
    if (!base || !enabled) return
    const controller = new AbortController()
    let active = true
    const timer = setTimeout(() => controller.abort(), 90000)
    setConnection('Connecting, the service may take a minute to wake')
    void Promise.all([
      fetch(base + '/healthz', {signal: controller.signal}),
      fetch(base + '/v1/catalog', {signal: controller.signal}),
    ]).then(async ([healthResponse, catalogResponse]) => {
      if ([healthResponse.status, catalogResponse.status].some(s => s === 401 || s === 403)) throw new Error('Private service, recorded evidence is available')
      if (!healthResponse.ok || !catalogResponse.ok) throw new Error('Service unavailable, recorded evidence is available')
      const [health, value] = await Promise.all([healthResponse.json(), catalogResponse.json()])
      if (!Array.isArray(value.tasks) || !Array.isArray(value.policies) || value.schema_version !== 1 || !value.configurations) throw new Error('Unsupported live catalog')
      if (controller.signal.aborted) return
      setCatalog(value)
      setConnection(health.live_enabled ? value.available ? 'Connected' : 'Live budget unavailable' : 'Live execution disabled')
    }).catch(error => {
      if (!active) return
      if (!controller.signal.aborted) { setCatalog(null); setConnection(error.message || 'Service unavailable') }
      else if (enabled) { setCatalog(null); setConnection('Connection timed out, the service may still be waking') }
    }).finally(() => clearTimeout(timer))
    return () => { active = false; clearTimeout(timer); controller.abort() }
  }, [base, enabled, check])

  useEffect(() => {
    if (!base || !state.runId || state.phase !== 'queued') return
    let cancelled = false, polls = 0
    let timer: ReturnType<typeof setTimeout> | undefined
    const controller = new AbortController()
    const runId = state.runId
    const deadlineTimer = setTimeout(() => setState(s => ({...s, phase: 'paused', message: 'The wait limit was reached. This run may still be pending. Check its status without submitting a replacement.'})), 680000)
    const poll = async () => {
      if (++polls > 170) { setState(s => ({...s, phase: 'paused', message: 'The wait limit was reached. This run may still be pending. Check its status without submitting a replacement.'})); return }
      try {
        const response = await fetch(base + '/v1/runs/' + runId, {signal: AbortSignal.any([controller.signal, AbortSignal.timeout(20000)])})
        if (!response.ok) throw new Error('Run status is unavailable. Keep this run ID and check again.')
        const result = await response.json()
        if (cancelled) return
        if (result.status === 'complete') {
          if (!result.result || result.result.id !== runId) throw new Error('The live result could not be verified. Keep the run ID and check again.')
          setState(s => ({...s, phase: 'complete', result: result.result, message: 'Live execution complete.'})); return
        }
        if (['failed', 'interrupted'].includes(result.status)) { setState(s => ({...s, phase: 'failed', message: typeof result.error === 'string' ? result.error : 'The live execution failed or was interrupted.'})); return }
        setState(s => ({...s, message: 'Live execution: ' + result.status + '. The recorded explorer remains available.'}))
        timer = setTimeout(poll, 4000)
      } catch (error) { if (!cancelled) setState(s => ({...s, phase: 'paused', message: error instanceof Error ? error.message : 'Run status unavailable.'})) }
    }
    void poll()
    return () => { cancelled = true; clearTimeout(timer); clearTimeout(deadlineTimer); controller.abort() }
  }, [base, state.runId, state.phase, pollVersion])

  async function submit(request: Submission, reuse?: {key: string}) {
    if (!base || locked.current || (!reuse && ['submitting', 'queued', 'uncertain', 'paused'].includes(state.phase))) return
    locked.current = true
    const key = reuse?.key || crypto.randomUUID()
    if (!reuse) submissionJudge.current = judge
    const code = submissionJudge.current
    setState({phase: 'submitting', key, request, message: 'Connecting to the live service. A sleeping service can take a minute to wake.'})
    try {
      const response = await fetch(base + '/v1/runs', {method: 'POST', signal: AbortSignal.timeout(90000),
        headers: {'Content-Type': 'application/json', 'Idempotency-Key': key, ...(code ? {'X-Judge-Code': code} : {})}, body: JSON.stringify(request)})
      const text = await response.text()
      let payload: {id?: string; status?: string; detail?: unknown}
      try { payload = JSON.parse(text) } catch { throw new Error('The service response was unreadable. Admission is uncertain.') }
      if (!response.ok) {
        const detail = typeof payload.detail === 'string' ? payload.detail : 'The live service could not accept the request.'
        const certain = (response.status >= 400 && response.status < 500 && response.status !== 408) || /no call was dispatched|execution is disabled/i.test(detail)
        setState({phase: certain ? 'failed' : 'uncertain', key, request, message: detail}); return
      }
      if (response.status !== 202 || typeof payload.id !== 'string' || !/^[\w-]+$/.test(payload.id)) throw new Error('No verifiable run ID was returned. Admission is uncertain.')
      setState({phase: 'queued', key, request, runId: payload.id, message: 'Run accepted. Waiting for its recorded result.'})
    } catch (error) { setState({phase: 'uncertain', key, request, message: (error instanceof Error ? error.message : 'Connection lost.') + ' A lost response does not mean no run was started.'}) }
    finally { locked.current = false }
  }
  return {catalog, connection, judge, setJudge, state, submit, reconnect: () => setCheck(c => c + 1), recover: () => state.key && state.request && submit(state.request, {key: state.key}), resume: () => {setPollVersion(v => v + 1); setState(s => ({...s, phase: 'queued'}))}}
}
export type LiveController = ReturnType<typeof useLiveRun>
