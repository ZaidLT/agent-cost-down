import {readFileSync} from 'node:fs'
const original = JSON.parse(readFileSync(new URL('../../public/reports/illustration.json', import.meta.url), 'utf8'))
import type { Catalog, Report } from '../../src/types'
// Synthetic test data only. These values are never included in production assets.
export function makeReport(version: 'v3' | 'v4' = 'v4'): Report {
  const report = structuredClone(original) as unknown as Report
  report.id = 'synthetic-' + version
  report.source = 'benchmark'
  report.split = 'heldout'
  report.provenance = {protocol_version: version === 'v4' ? '4' : '3', limitations: 'SYNTHETIC TEST FIXTURE. Not real model evidence.', paired: [
    {policy:'small_ultra',task_id:'synthetic-1',repetition:0,success:true,ultra_success:true},
    {policy:'small_ultra',task_id:'synthetic-2',repetition:0,success:true,ultra_success:false},
    {policy:'small_ultra',task_id:'synthetic-3',repetition:0,success:false,ultra_success:true},
    {policy:'small_ultra',task_id:'synthetic-4',repetition:0,success:false,ultra_success:false},
  ]}
  report.recommendation = {selected:'small_ultra',status:version === 'v4' ? 'validated' : 'not_validated',reason:'SYNTHETIC TEST: recommendation status.'}
  const costs=[0.07080264,0.16674870,0.472687,0.07475934,0.12071164]
  const successes=[52,52,57,55,57]
  report.policies = report.policies.map((p,i)=>({...p,assigned:60,completed:60,successes:successes[i],success_rate:successes[i]/60,total_estimated_usd:costs[i],median_ms:p.id==='ultra_only'?5449.59:18909.81,savings_vs_ultra:p.id==='small_ultra'?0.7446269:0}))
  report.runs=report.runs.map((r,i)=>({...r,id:'synthetic-run-'+i,source:'benchmark',task:{...r.task,id:'synthetic-task-'+i,request:'Synthetic test request '+i},policy:{...r.policy,validator_version:version==='v4'?'2':'1',models:r.policy.models.map(m=>({...m,id:m.id.replace('test-small','nvidia/Nemotron-3-Nano').replace('test-ultra','nvidia/Nemotron-3-Ultra').replace('test-super','nvidia/Nemotron-3-Super')}))}}))
  return report
}
export function makeCatalog(report: Report): Catalog {return {schema_version:1,tasks:['resolution-development-1'],policies:report.policies.map(p=>p.id),configurations:Object.fromEntries(report.runs.map(r=>[r.policy.id,r.policy])),policy_hashes:{},available:true}}
export const scriptedReport = structuredClone(original) as unknown as Report
