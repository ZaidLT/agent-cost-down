import { test, expect } from '@playwright/test'

test('comparison, independent outcome, policy export, disconnected API', async ({page}) => {
  await page.goto('/')
  await expect(page.getByText('Scripted illustration. No real model results or cost savings have been measured.')).toBeVisible()
  await expect(page.getByRole('heading', {name: 'Awaiting model evidence'})).toBeVisible()
  await page.getByRole('link', {name: 'Inspect Small + Ultra', exact: true}).click()
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
