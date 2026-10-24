import { chromium } from '@playwright/test'
import { mkdir, copyFile } from 'node:fs/promises'
import path from 'node:path'

const output = path.resolve('../artifacts/youtube-test')
await mkdir(output, {recursive: true})
const browser = await chromium.launch({headless: true})
const context = await browser.newContext({
  viewport: {width: 1280, height: 720},
  recordVideo: {dir: output, size: {width: 1280, height: 720}},
})
const page = await context.newPage()
await page.goto('http://127.0.0.1:5178')
await page.getByRole('heading', {name: 'Awaiting model evidence'}).waitFor()
await page.waitForTimeout(4000)
await page.getByRole('link', {name: 'Inspect Small + Ultra', exact: true}).click()
await page.waitForTimeout(4000)
await page.getByRole('link', {name: 'Apply this policy'}).click()
await page.waitForTimeout(4000)
await context.close()
const video = await page.video().path()
await copyFile(video, path.join(output, 'upload-test-silent.webm'))
await browser.close()
process.stdout.write('Saved a silent UI upload-test clip. It is explicitly a scripted illustration, not the submission video.\n')
