import {test,expect} from '@playwright/test'
import {readFileSync} from 'node:fs'
import {attemptCause,diagnosis,exportedPolicy,finalCause,pairedCounts,stateDiff} from '../src/lib/evidence'
import {makeReport} from './fixtures/reports'
import type {Report} from '../src/types'
test('verified contract map matches original immutable v3 report and final categories reconcile',()=>{
 const report=JSON.parse(readFileSync(new URL('../public/reports/555720dd79a2c26c.json',import.meta.url),'utf8')) as Report
 const groups=diagnosis(report)
 expect(groups.final.contract).toHaveLength(33)
 expect(Object.values(groups.final).flat()).toHaveLength(52)
 expect(new Set(Object.values(groups.final).flat().map(r=>r.id)).size).toBe(52)
 expect(Object.fromEntries(report.policies.map(p=>[p.id,groups.final.contract.filter(r=>r.policy.id===p.id).length]))).toEqual({small_only:10,small_retry:3,small_ultra:4,super_only:4,ultra_only:12})
 const legacy=report.runs.flatMap(run=>run.attempts.map((attempt,index)=>({run,attempt,index}))).filter(({attempt})=>attempt.events.some(e=>e.code==='NO_TOOL_CALL'))
 expect(legacy).toHaveLength(14)
 for(const {run,index} of legacy)expect(attemptCause(report,run,index)).toBe('missing')
})
test('failure classification covers all evidence types without guessing a contract defect',()=>{
 const report=makeReport();const run=report.runs[0];run.outcome!.success=false;run.verdict='UNRESOLVED';const a=run.attempts[0]
 for(const [reason,code,kind,expected] of [
 ['runtime_validation_failed','BUSINESS_RULE_VIOLATION','tool','runtime'],['parse_failed','INVALID_JSON','failure','json'],['tool_schema_failed','INVALID_ARGUMENT_TYPE','failure','schema'],['','DEADLINE_EXCEEDED','failure','deadline'],['','','provider_failure','provider'],['','','unknown','unclassified'],['parse_failed','NO_TOOL_CALL','failure','missing'],
 ]){a.failure_context={reason,observations:[{code}]};a.events=[{kind,code}];expect(finalCause(report,run)).toBe(expected)}
 run.verdict='CLARIFY';run.outcome!.checks.response=false;expect(finalCause(report,run)).toBe('clarification')
 run.verdict='ACCEPT';expect(finalCause(report,run)).toBe('incorrect')
 run.outcome=null;expect(finalCause(report,run)).not.toBe('incorrect')
 run.outcome={success:true,critical_error:false,checks:{}};expect(finalCause(report,run)).toBeNull()
})
test('paired outcomes are paired observations, not an equivalence claim',()=>{expect(pairedCounts(makeReport(),'small_ultra')).toEqual({both:1,policy:1,ultra:1,neither:1})})
test('state diff captures additions, removals, quantities, returns, SKU and inventory',()=>{
 const result=stateDiff({lines:[{id:'L1',quantity:2,sku:'A',returned:0},{id:'gone',quantity:1}],stock:[{sku:'A',available:25}]},{lines:[{id:'L1',quantity:9,sku:'B',returned:1},{id:'new',quantity:4}],stock:[{sku:'A',available:18}]})
 expect(result.map(r=>r.field)).toEqual(['quantity','sku','returned','Removed','Added','available'])
 expect(result.find(r=>r.field==='quantity')).toMatchObject({before:2,after:9})
 expect(stateDiff({},{})).toEqual([])
})
test('policy export preserves unknown fields, nested settings and every limit',()=>{
 const config=makeReport().runs[0].policy;config.extra_future_field={untouched:true};config.models[0].settings={temperature:0,seed:42};config.limits.extra_limit=17
 const exported=JSON.parse(JSON.stringify(exportedPolicy(config,'synthetic-report')))
 expect(exported).toEqual({...config,supporting_report:'synthetic-report'});expect(config.supporting_report).not.toBe('synthetic-report')
})
