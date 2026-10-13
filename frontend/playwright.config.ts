import { defineConfig, devices } from '@playwright/test'

// The isolated stack `wl e2e` starts (docker-compose.e2e.yml) serves the web app here, seeded
// with the demo data (`wl seed --demo`).
const BASE_URL = 'http://localhost:5174'

export default defineConfig({
  testDir: './e2e',
  // One worker: every test shares the one seeded stack.
  workers: 1,
  forbidOnly: Boolean(process.env.CI),
  reporter: 'list',
  use: { baseURL: BASE_URL, trace: 'retain-on-failure' },
  // Every flow runs once per theme, so its axe checks cover both (docs/ui-design-guide.md §9).
  projects: [
    { name: 'light', use: { ...devices['Desktop Chrome'], colorScheme: 'light' } },
    { name: 'dark', use: { ...devices['Desktop Chrome'], colorScheme: 'dark' } },
  ],
})
