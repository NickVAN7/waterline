import { defineConfig, devices } from '@playwright/test'

import base from './playwright.config'

// The guide's screenshots (DL-343), run by `wl docs-screenshots` on the end-to-end stack: never
// part of `wl e2e`, whose config matches only `*.spec.ts`.
export default defineConfig({
  ...base,
  testDir: './e2e/screenshots',
  testMatch: '*.shot.ts',
  // Wide enough for the split pane beside a list, as on a desktop screen.
  projects: ['light', 'dark'].map((theme) => ({
    name: theme,
    use: {
      ...devices['Desktop Chrome'],
      viewport: { width: 1440, height: 900 },
      colorScheme: theme as 'light' | 'dark',
    },
  })),
})
