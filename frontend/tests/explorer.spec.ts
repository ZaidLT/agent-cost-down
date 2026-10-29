import { test, expect } from '@playwright/test'

// Keep scripted behavior tests independent of the report selected for release.
test.beforeEach(async ({page}) => {
  await page.route('**/reports/index.json', route => route.fulfill({json: {active: 'illustration.json', status: 'test_fixture'}}))
})

test('comparison, independent outcome, policy export, disconnected API', async ({page}) => {
  await page.goto('/')
  await expect(page.getByText('Scripted illustration. No real model results or cost savings have been measured.')).toBeVisible()
  await expect(page.getByRole('heading', {name: 'Awaiting model evidence'})).toBeVisible()
  await page.getByRole('link', {name: 'Inspect Nano + Ultra', exact: true}).click()
  await expect(page.getByRole('heading', {name: 'Independent outcome'})).toBeVisible()
  await expect(page.getByText('Restart from the original state')).toBeVisible()
  await page.getByRole('link', {name: 'Apply this policy'}).click()
  await expect(page.getByRole('button', {name: 'Start live sample'})).toBeDisabled()
  await expect(page.getByText('Live execution is not connected. The report explorer works independently.')).toBeVisible()
  const download = page.waitForEvent('download')
  await page.getByRole('button', {name: 'Download policy.json'}).click()
  expect((await download).suggestedFilename()).toBe('policy.json')
})

test('mobile layout and deep link survive refresh', async ({page}) => {
  await page.setViewportSize({width: 390, height: 844})
  await page.goto('/#inspect')
  await expect(page.getByRole('heading', {name: 'Inspect an execution', exact: true})).toBeVisible()
  await page.reload()
  await expect(page.getByRole('heading', {name: 'Independent outcome'})).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBeTruthy()
  await page.screenshot({path: 'test-results/mobile.png', fullPage: true})
})

test('keyboard focus and report loading failure are usable', async ({page}) => {
  await page.goto('/')
  await page.keyboard.press('Tab')
  await expect(page.getByRole('link', {name: 'Skip to content'})).toBeFocused()
  await page.route('**/reports/index.json', route => route.abort())
  await page.reload()
  await expect(page.getByRole('heading', {name: 'The report could not be loaded.'})).toBeVisible()
  await expect(page.getByRole('button', {name: 'Reload report'})).toBeVisible()
})

test('desktop evidence layout', async ({page}) => {
  await page.setViewportSize({width: 1440, height: 1000})
  await page.goto('/')
  await expect(page.getByRole('heading', {name: 'Five policies, one workload'})).toBeVisible()
  await page.screenshot({path: 'test-results/desktop.png', fullPage: true})
})

test('measured validated report shows the headline result', async ({page}) => {
  const base = await (await page.request.get('/reports/illustration.json')).json()
  const report = {...base, source: 'benchmark', split: 'heldout',
    runs: base.runs.map((r: any) => ({...r, policy: {...r.policy, models: r.policy.models.map((m: any) => ({...m, id: m.id.replace('small', 'Nano')}))}})),
    recommendation: {selected: 'small_ultra', status: 'validated', reason: 'Selected on development data and passed held-out gates.'},
    policies: base.policies.map((p: Record<string, unknown>) => ({...p, total_estimated_usd: 0.01, savings_vs_ultra: p.id === 'small_ultra' ? 0.42 : null}))}
  await page.route('**/reports/index.json', route => route.fulfill({json: {active: 'measured.json', status: 'recorded'}}))
  await page.route('**/reports/measured.json', route => route.fulfill({json: report}))
  await page.goto('/')
  await expect(page.getByRole('heading', {name: 'Nano + Ultra'})).toBeVisible()
  await expect(page.getByText('42.0% less estimated spend than Ultra only')).toBeVisible()
})

for (const scenario of ['missing savings', 'development only', 'not validated']) {
  test(`headline is hidden for ${scenario}`, async ({page}) => {
    const base = await (await page.request.get('/reports/illustration.json')).json()
    const report = {...base, source: 'benchmark', split: scenario === 'development only' ? 'development' : 'heldout',
      recommendation: {selected: 'small_ultra', status: scenario === 'not validated' ? 'not_validated' : 'validated', reason: 'Test scenario'},
      policies: base.policies.map((p: Record<string, unknown>) => ({...p, savings_vs_ultra: scenario === 'missing savings' ? null : 0.42}))}
    await page.route('**/reports/index.json', route => route.fulfill({json: {active: 'case.json'}}))
    await page.route('**/reports/case.json', route => route.fulfill({json: report}))
    await page.goto('/')
    await expect(page.getByRole('heading', {name: 'Five policies, one workload'})).toBeVisible()
    await expect(page.getByText(/less estimated spend than Ultra only/)).toHaveCount(0)
  })
}

test('substituted model identity remains visible', async ({page}) => {
  const base = await (await page.request.get('/reports/illustration.json')).json()
  const report = {...base, source: 'benchmark', runs: base.runs.map((r: any) => ({...r,
    policy: {...r.policy, models: r.policy.models.map((m: any, i: number) => ({...m, id: r.policy.id.startsWith('small') && i === 0 ? 'nvidia/Nemotron-3_5-Lightning' : m.id}))}}))}
  await page.route('**/reports/index.json', route => route.fulfill({json: {active: 'substitution.json'}}))
  await page.route('**/reports/substitution.json', route => route.fulfill({json: report}))
  await page.goto('/')
  await expect(page.getByRole('link', {name: 'Inspect Lightning only', exact: true})).toBeVisible()
})
