import { defineConfig } from '@playwright/test'
export default defineConfig({
  testDir: './tests',
  fullyParallel: true,
  workers: 4,
  use: {baseURL: 'http://127.0.0.1:5186', headless: true, trace: 'retain-on-failure'},
  webServer: {command: 'node scripts/test-server.mjs', url: 'http://127.0.0.1:5186', reuseExistingServer: false},
})
