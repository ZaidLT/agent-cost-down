import {test, expect} from '@playwright/test'

test('controlled rerun disclosure is visible across routes', async ({page}) => {
  const base = await (await page.request.get('/reports/illustration.json')).json()
  const disclosure = 'Controlled rerun on the same evaluation suite. These tasks and their v3 results were inspected before the v4 amendment. This is not fresh independent validation.'
  await page.route('**/reports/index.json', route => route.fulfill({json: {active: 'rerun.json', reports: [{file: 'original.json', label: 'v3 original study'}, {file: 'rerun.json', label: 'v4 controlled rerun'}]}}))
  await page.route('**/reports/rerun.json', route => route.fulfill({json: {...base, provenance: {...base.provenance, evaluation_disclosure: disclosure}}}))
  await page.goto('/')
  await expect(page.getByText(disclosure, {exact: true})).toBeVisible()
  await expect(page.getByRole('navigation', {name: 'Experiment versions'})).toBeVisible()
  await page.getByRole('link', {name: 'Apply', exact: true}).click()
  await expect(page.getByText(disclosure, {exact: true})).toBeVisible()
})
