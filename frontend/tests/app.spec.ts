import {test,expect,type Page} from '@playwright/test'
import {makeReport,makeCatalog} from './fixtures/reports'
const api='http://127.0.0.1:5499'
async function setup(page:Page,{mismatch=false,privateService=false,available=true}={}){
 const report=makeReport();const catalog=makeCatalog(report);catalog.available=available
 if(mismatch)catalog.configurations.small_ultra={...catalog.configurations.small_ultra,validator_version:'999'}
 await page.route('**/reports/index.json',r=>r.fulfill({json:{active:'synthetic.json'}}));await page.route('**/reports/synthetic.json',r=>r.fulfill({json:report}))
 await page.route(api+'/healthz',r=>r.fulfill({status:privateService?401:200,json:{status:'ok',live_enabled:true}}))
 await page.route(api+'/v1/catalog',r=>r.fulfill({status:privateService?401:200,json:catalog}))
 await page.goto('/#apply/small_ultra')
 return report
}
test('configuration mismatch disables live execution while export stays available',async({page})=>{
 await setup(page,{mismatch:true});await expect(page.getByText(/Configuration mismatch/)).toBeVisible();await expect(page.getByRole('button',{name:'Start live sample'})).toBeDisabled();await expect(page.getByRole('button',{name:'Download policy.json'})).toBeEnabled()
})
test('protected API preserves static export and explains its status',async({page})=>{
 await setup(page,{privateService:true});await expect(page.getByText('Private service, recorded evidence is available',{exact:true})).toBeVisible();await expect(page.getByRole('button',{name:'Start live sample'})).toBeDisabled();await expect(page.getByRole('button',{name:'Download policy.json'})).toBeEnabled()
 await page.getByRole('link',{name:'Inspect a recorded execution'}).click();await expect(page.getByRole('heading',{name:'Execution evidence'})).toBeVisible();await expect(page.getByText('Recorded model execution',{exact:true})).toBeVisible()
})
test('cold start is visible and catalog/health must finish before enabling execution',async({page})=>{
 await setup(page);await page.route(api+'/healthz',async r=>{await new Promise(resolve=>setTimeout(resolve,500));await r.fulfill({json:{status:'ok',live_enabled:true}})})
 await page.getByRole('button',{name:'Check connection'}).click();await expect(page.getByText('Connecting, the service may take a minute to wake',{exact:true})).toBeVisible();await expect(page.getByRole('button',{name:'Start live sample'})).toBeDisabled();await expect(page.getByRole('button',{name:'Start live sample'})).toBeEnabled()
})
test('quota denial is explicit and dispatch is never replaced automatically',async({page})=>{
 let posts=0;await setup(page);await page.route(api+'/v1/runs',r=>{posts++;return r.fulfill({status:429,json:{detail:'Public quota exhausted. Try after the quota resets.'}})})
 await expect(page.getByRole('button',{name:'Start live sample'})).toBeEnabled();await page.getByRole('button',{name:'Start live sample'}).click();await expect(page.getByText('Public quota exhausted. Try after the quota resets.')).toBeVisible();expect(posts).toBe(1)
})
test('uncertain response retains a key and recovery reuses exactly the same submission',async({page})=>{
 const requests:{key:string|undefined,body:string|null}[]=[];const report=await setup(page)
 await page.route(api+'/v1/runs',r=>{requests.push({key:r.request().headers()['idempotency-key'],body:r.request().postData()});return requests.length===1?r.abort():r.fulfill({status:202,json:{id:'synthetic-live',status:'queued'}})})
 await page.route(api+'/v1/runs/synthetic-live',r=>r.fulfill({json:{id:'synthetic-live',status:'complete',result:{...report.runs.find(r=>r.policy.id==='small_ultra'),id:'synthetic-live',source:'live'},error:null}}))
 await expect(page.getByRole('button',{name:'Start live sample'})).toBeEnabled();await page.getByLabel('Judge access code (optional)').fill('synthetic-code')
 await page.getByRole('button',{name:'Start live sample'}).click();await expect(page.getByText('Admission uncertain',{exact:true})).toBeVisible();await expect(page.getByRole('button',{name:'Start live sample'})).toBeDisabled()
 await page.getByRole('link',{name:/Compare$/}).click();await page.getByRole('link',{name:/Apply$/}).click()
 await expect(page.getByText('Admission uncertain',{exact:true})).toBeVisible();await page.getByRole('button',{name:'Recover the same request'}).click();await expect(page.getByRole('heading',{name:'Your live result'})).toBeVisible()
 expect(requests).toHaveLength(2);expect(requests[1]).toEqual(requests[0]);expect(requests[0].key).toBeTruthy()
 expect(await page.evaluate(()=>JSON.stringify({...localStorage}))).not.toContain('synthetic-code')
})
test('uncertain server dispatch never becomes a new logical submission',async({page})=>{
 await setup(page);await page.route(api+'/v1/runs',r=>r.fulfill({status:503,json:{detail:'Queue dispatch uncertain; check this request using the same idempotency key'}}))
 await expect(page.getByRole('button',{name:'Start live sample'})).toBeEnabled();await page.getByRole('button',{name:'Start live sample'}).click();await expect(page.getByText('Admission uncertain',{exact:true})).toBeVisible();await expect(page.getByRole('button',{name:'Recover the same request'})).toBeVisible()
})
test('failed status lookup retains run identity and manual retry only polls the original',async({page})=>{
 let posts=0,polls=0;await setup(page)
 await page.route(api+'/v1/runs',r=>{posts++;return r.fulfill({status:202,json:{id:'retained-run',status:'queued'}})})
 await page.route(api+'/v1/runs/retained-run',r=>{polls++;return polls===1?r.fulfill({status:503,json:{detail:'Unavailable'}}):r.fulfill({json:{id:'retained-run',status:'failed',error:'Synthetic execution failure',result:null}})})
 await expect(page.getByRole('button',{name:'Start live sample'})).toBeEnabled();await page.getByRole('button',{name:'Start live sample'}).click();await expect(page.getByText('Status check paused',{exact:true})).toBeVisible();await expect(page.getByText('retained-run',{exact:true})).toBeVisible();await page.getByRole('button',{name:'Check this run’s status'}).click();await expect(page.getByText('Synthetic execution failure')).toBeVisible();expect(posts).toBe(1)
})
test('bounded polling stops and retains the existing run ID',async({page})=>{
 await page.clock.install();await setup(page)
 let polls=0;await page.route(api+'/v1/runs',r=>r.fulfill({status:202,json:{id:'bounded-run',status:'queued'}}));await page.route(api+'/v1/runs/bounded-run',r=>{polls++;return r.fulfill({json:{id:'bounded-run',status:'queued',result:null,error:null}})})
 await expect(page.getByRole('button',{name:'Start live sample'})).toBeEnabled();await page.getByRole('button',{name:'Start live sample'}).click()
 await expect(page.getByText('bounded-run',{exact:true})).toBeVisible()
 await expect.poll(()=>polls).toBeGreaterThan(0)
 await page.clock.fastForward(681000)
 await expect(page.getByText('Status check paused',{exact:true})).toBeVisible();expect(polls).toBeLessThanOrEqual(170);expect(polls).toBeGreaterThan(0);await expect(page.getByText('bounded-run',{exact:true})).toBeVisible()
})
test('a submission timeout retains the request instead of starting another run',async({page})=>{
 await page.addInitScript(()=>{const original=AbortSignal.timeout.bind(AbortSignal);AbortSignal.timeout=(ms:number)=>original(ms===90000?50:ms)})
 await setup(page);let posts=0;await page.route(api+'/v1/runs',()=>{posts++})
 await expect(page.getByRole('button',{name:'Start live sample'})).toBeEnabled();await page.getByRole('button',{name:'Start live sample'}).click();await expect(page.getByText('Admission uncertain',{exact:true})).toBeVisible();await expect(page.getByRole('button',{name:'Start live sample'})).toBeDisabled();expect(posts).toBe(1)
})
