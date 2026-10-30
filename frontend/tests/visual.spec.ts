import {test,expect} from '@playwright/test'
import {readFileSync,existsSync} from 'node:fs'
import type {Report} from '../src/types'
const path=new URL('../../artifacts/frontend-preview/135c81cc2a5991c2.json',import.meta.url)
const available=existsSync(path)
// Optional integration review: exact immutable report bytes, never synthetic screenshots.
for(const width of [390,768,1440])test('real v4 visual review at '+width,async({page})=>{
 test.skip(!available,'Local exact v4 preview copy is not present; the synthetic suite remains independent.')
 const body=readFileSync(path,'utf8');const report=JSON.parse(body) as Report
 await page.route('**/reports/index.json',r=>r.fulfill({json:{active:'135c81cc2a5991c2.json',status:'local_preview'}}))
 await page.route('**/reports/135c81cc2a5991c2.json',r=>r.fulfill({body,contentType:'application/json'}))
 await page.route('**/healthz',r=>r.fulfill({status:503,json:{detail:'Disconnected visual review'}}));await page.route('**/v1/catalog',r=>r.fulfill({status:503,json:{detail:'Disconnected visual review'}}))
 await page.setViewportSize({width,height:width===390?844:900})
 const recovery=report.runs.find(r=>r.policy.id==='small_ultra'&&r.attempts.length>1&&r.outcome?.success)!
 for(const [screen,route] of [['compare','compare'],['inspect','inspect/'+recovery.id],['apply','apply/small_ultra']]){
  await page.goto('/#'+route);await expect(page.locator('h1')).toBeVisible();await page.evaluate(()=>document.fonts.ready)
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy()
  if(width===1440 && screen==='compare'){await expect(page.getByText('Scoring-sensitive result.',{exact:true})).toBeInViewport();await expect(page.getByText('74.5%',{exact:true})).toBeInViewport()}
  await page.screenshot({path:`test-results/screenshots/${screen}-${width}.png`,fullPage:true})
  await page.screenshot({path:`test-results/screenshots/${screen}-${width}-viewport.png`})
 }
})
