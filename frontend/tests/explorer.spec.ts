import {test,expect,type Page} from '@playwright/test'
import {readFile} from 'node:fs/promises'
import {makeReport,scriptedReport} from './fixtures/reports'
import {disclosure} from '../src/lib/evidence'
import type {Report} from '../src/types'
async function serve(page:Page, report:Report=makeReport()){
 await page.route('**/reports/index.json',r=>r.fulfill({json:{active:'case.json',reports:[{file:'case.json',label:'Synthetic v4 test'},{file:'v3.json',label:'Synthetic v3 test'}]}}))
 await page.route('**/reports/case.json',r=>r.fulfill({json:report}))
 await page.route('**/reports/v3.json',r=>r.fulfill({json:makeReport('v3')}))
 await page.route('**/healthz',r=>r.fulfill({status:503,json:{detail:'Disconnected test service'}}))
 await page.route('**/v1/catalog',r=>r.fulfill({status:503,json:{detail:'Disconnected test service'}}))
}
test('v4 first screen presents cost, correctness, speed and immutable recommendation',async({page})=>{
 await serve(page);await page.goto('/')
 await expect(page.getByText('57/60 correct',{exact:true})).toBeVisible()
 await expect(page.getByText('74.5%',{exact:true})).toBeVisible()
 await expect(page.getByText('18.91 s',{exact:true}).first()).toBeVisible()
 await expect(page.getByText(/Ultra: 5.45 s/)).toBeVisible()
 await page.getByRole('button',{name:'Ultra Faster'}).click()
 await expect(page.getByText('Recorded result',{exact:true})).toBeVisible()
 await page.getByText('View accessible comparison table and measurement details').click()
 await expect(page.getByRole('region',{name:'Policy comparison table'}).getByRole('table')).toBeVisible()
 await expect(page.getByRole('columnheader',{name:'p95 time'})).toBeVisible()
})
test('v3 and v4 selection, browser history and deep links survive refresh',async({page})=>{
 const report=makeReport();await serve(page,report);await page.goto('/?report=v3.json#inspect/synthetic-run-0')
 await expect(page.getByRole('heading',{name:'Execution evidence'})).toBeVisible()
 await expect(page.getByText(disclosure,{exact:true})).toHaveCount(0)
 await page.getByLabel('Experiment version').selectOption('case.json')
 await expect(page).toHaveURL(/report=case.json#compare/)
 await expect(page.getByText(disclosure,{exact:true})).toBeVisible()
 await page.goBack();await expect(page.getByRole('heading',{name:'Execution evidence'})).toBeVisible()
 await page.reload();await expect(page.getByRole('heading',{name:'Execution evidence'})).toBeVisible()
})
test('v4 disclosure is visible on every route, even with missing provenance disclosure',async({page})=>{
 await serve(page);await page.goto('/')
 for(const name of ['Compare','Inspect','Apply']){await page.getByRole('link',{name:new RegExp(name+'$')}).click();await expect(page.getByText(disclosure,{exact:true})).toBeVisible()}
})
test('scripted reports cannot claim model savings or enable inference',async({page})=>{
 await serve(page,scriptedReport);await page.goto('/')
 await expect(page.getByText('Scripted illustration. No real model results or cost savings have been measured.')).toBeVisible()
 await expect(page.getByText('74.5%',{exact:true})).toHaveCount(0)
 await page.getByRole('link',{name:/Apply$/}).click()
 await expect(page.getByRole('button',{name:'Start live sample'})).toBeDisabled()
})
test('diagnosis categories link to the actual selected-report run',async({page})=>{
 const report=makeReport();const failure=report.runs[0];failure.outcome!.success=false;failure.outcome!.checks.response=false;failure.verdict='ACCEPT'
 await serve(page,report);await page.goto('/')
 await page.getByText('Incorrect accepted outcome',{exact:true}).click()
 await page.getByRole('link',{name:new RegExp(failure.task.id+', repeat')}).click()
 await expect(page).toHaveURL(new RegExp('#inspect/'+failure.id+'$'))
 await expect(page.getByRole('heading',{name:failure.task.request})).toBeVisible()
 await expect(page.getByText('Incorrect outcome',{exact:true})).toBeVisible()
 await expect(page.getByText('Accepted by runtime',{exact:true}).first()).toBeVisible()
})
test('readable state diffs, recovery timeline, raw evidence and export',async({page})=>{
 const report=makeReport();const recovery=report.runs.find(r=>r.attempts.length>1 && r.outcome?.success)!
 await serve(page,report);await page.goto('/#inspect/'+recovery.id)
 await expect(page.getByRole('heading',{name:'What changed'})).toBeVisible()
 await expect(page.getByText('Order line / sku')).toBeVisible()
 await expect(page.getByText('Clean restart from the original state')).toBeVisible()
 await expect(page.getByRole('heading',{name:'Independent outcome'})).toBeVisible()
 await page.getByText('Original and final state JSON',{exact:true}).click()
 await expect(page.locator('pre[aria-label="Original and final state JSON"]')).toBeVisible()
 await page.getByRole('link',{name:'Apply this policy'}).click()
 const download=page.waitForEvent('download');await page.getByRole('button',{name:'Download policy.json'}).click()
 const path=await(await download).path();const data=JSON.parse(await readFile(path!,'utf8'))
 expect(data).toEqual({...recovery.policy,supporting_report:report.id})
})
test('invalid execution deep links never silently show another run',async({page})=>{
 await serve(page);await page.goto('/#inspect/not-a-real-run')
 await expect(page.getByRole('heading',{name:'Execution not found'})).toBeVisible()
 await expect(page.getByRole('heading',{name:'Independent outcome'})).toHaveCount(0)
})
test('report failure offers retry and keyboard skip link focuses main content',async({page})=>{
 await serve(page);await page.goto('/');await page.keyboard.press('Tab')
 await expect(page.getByRole('link',{name:'Skip to content'})).toBeFocused()
 await page.keyboard.press('Enter');await expect(page.locator('main')).toBeFocused()
 await page.route('**/reports/index.json',r=>r.abort());await page.reload()
 await expect(page.getByRole('heading',{name:'The report could not be loaded.'})).toBeVisible()
 await page.unroute('**/reports/index.json');await serve(page)
 await page.getByRole('button',{name:'Reload report'}).click();await expect(page.getByRole('heading',{level:1})).toBeVisible()
})
for(const scenario of ['development','not validated','missing savings'])test('savings headline is gated for '+scenario,async({page})=>{
 const report=makeReport();if(scenario==='development')report.split='development';if(scenario==='not validated')report.recommendation.status='not_validated';if(scenario==='missing savings')report.policies.forEach(p=>p.savings_vs_ultra=null)
 await serve(page,report);await page.goto('/');await expect(page.getByRole('heading',{name:'Five policies. The same workload.'})).toBeVisible();await expect(page.getByText('74.5%',{exact:true})).toHaveCount(0)
})
for(const width of [360,390,768,1440])test('responsive screens and reduced motion at '+width,async({page})=>{
 await page.setViewportSize({width,height:900});await page.emulateMedia({reducedMotion:'reduce'});await serve(page)
 for(const route of ['compare','inspect','apply']){await page.goto('/#'+route);await expect(page.locator('h1')).toBeVisible();expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();await page.screenshot({path:`test-results/synthetic-${route}-${width}.png`,fullPage:true})}
 expect(await page.getByRole('button',{name:'Start live sample'}).evaluate(el=>getComputedStyle(el).transitionDuration)).toBe('0s')
})
test('actual substituted model identity stays visible',async({page})=>{
 const report=makeReport();report.runs.forEach(r=>{if(r.policy.id.startsWith('small'))r.policy.models[0].id='nvidia/Nemotron-3_5-Lightning'})
 await serve(page,report);await page.goto('/');await expect(page.getByText('Lightning',{exact:true}).first()).toBeVisible()
})
test('long identifiers and requests remain usable on a narrow screen',async({page})=>{
 const report=makeReport();report.runs[0].task.request='Synthetic stress test: '+ 'VeryLongUnbrokenRequest'.repeat(30);report.runs[0].policy.models[0].id='SyntheticModel'.repeat(30)
 await page.setViewportSize({width:360,height:844});await serve(page,report)
 for(const route of ['compare','inspect/'+report.runs[0].id,'apply/small_only']){await page.goto('/#'+route);await expect(page.locator('h1')).toBeVisible();expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),route).toBeTruthy()}
})
test('the published report index loads without a preview overlay',async({page})=>{
 const index=await(await page.request.get('/reports/index.json')).json()
 const report=await(await page.request.get('/reports/'+index.active)).json()
 await page.goto('/')
 await expect(page.getByRole('heading',{level:1})).toBeVisible()
 await expect(page.getByText('Report '+report.id,{exact:true})).toBeVisible()
})

test('real report makes scoring sensitivity prominent and compares original failures',async({page})=>{
 await page.goto('/');await expect(page.getByText('Scoring-sensitive result.',{exact:true})).toBeVisible()
 const summary=page.getByRole('region',{name:'Scoring sensitivity summary'})
 await expect(summary.getByRole('row',{name:'Pre-declared 57/60 57/60'})).toBeVisible()
 await expect(summary.getByRole('row',{name:'Broader clarification 60/60 57/60'})).toBeVisible()
 await expect(page.getByRole('heading',{level:1})).toContainText('74.5% lower estimated AI cost than Ultra.')
 await page.getByRole('link',{name:'See the scoring sensitivity'}).click()
 await expect(page.getByRole('heading',{name:'How clarification scoring changes the comparison'})).toBeInViewport()
 await expect(page.getByText(/post-hoc sensitivity analysis, not new model runs/)).toBeVisible()
 await expect(page.getByText('Declared criteria met',{exact:true})).toHaveCount(0)
 await expect(page.getByRole('button',{name:/empty categories/})).toHaveCount(0)
 const diagnosis=page.getByRole('region',{name:'Why did runs fail?'})
 await expect(diagnosis.locator('details > summary')).toHaveText(['Inspect recovered attempts'])
 await expect(diagnosis.locator('aside').getByText('12',{exact:true})).toBeVisible()
 const comparison=page.getByRole('region',{name:'Original and amended failure comparison'})
 await expect(comparison.getByRole('row',{name:'Total final failures 52 27'})).toBeVisible()
 const contractRow=comparison.getByRole('row').filter({has:page.getByRole('rowheader',{name:'Our runtime rejected unchanged fields',exact:true})});await expect(contractRow.getByRole('cell')).toHaveText(['33','0'])
 await expect(page.getByText('1 incorrect accepted outcome.',{exact:false})).toBeVisible()
 await page.getByLabel('Experiment version').selectOption('555720dd79a2c26c.json')
 await expect(page.getByRole('link',{name:'Inspect a recovery',exact:true})).toHaveCount(0)
 await expect(page.getByText('We kept the preselected policy and reported its failure.',{exact:true})).toBeVisible()
})
