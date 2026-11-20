/**
 * S3-C0n's screenshots of the trial screen, the requirement detail panel, copied into the trial
 * clone by `setup.py`. `wl docs-screenshots` runs it beside the guide's shots (its config takes
 * every `*.shot.ts`), on the end-to-end stack seeded with the manual pass's data, in light and
 * dark. Each shot is a PNG in `trial-shots/<TRIAL_SHOTS>/` at the clone's root (`baseline` unless
 * set, e.g. `TRIAL_SHOTS=after uv run wl docs-screenshots`).
 */
import { mkdirSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

import { expect, test } from '@playwright/test'

import { signIn } from '../support/demo'

const OUT = fileURLToPath(
  new URL(`../../../trial-shots/${process.env.TRIAL_SHOTS ?? 'baseline'}/`, import.meta.url),
)

const WIDTHS = [
  { width: 375, height: 812 },
  { width: 1280, height: 800 },
  { width: 1920, height: 1080 },
]

for (const viewport of WIDTHS) {
  test(`requirement panel at ${viewport.width}`, async ({ page }, testInfo) => {
    await page.setViewportSize(viewport)
    await signIn(page, 'lena')
    await page.goto('/acme/projects/PORTAL/requirements?open=RQ-2')
    // The panel's header, drawn in both layouts: a split pane from 64rem, a modal dialog below.
    await expect(page.getByRole('button', { name: 'Copy link' })).toBeVisible()
    await page.waitForLoadState('networkidle')
    await expect(page.locator('[aria-busy="true"]')).toHaveCount(0)
    await page.evaluate(() => (document.activeElement as HTMLElement | null)?.blur())

    mkdirSync(OUT, { recursive: true })
    const suffix = testInfo.project.name === 'dark' ? '-dark' : ''
    await page.screenshot({
      path: `${OUT}requirement-panel-${viewport.width}${suffix}.png`,
      fullPage: true,
    })
  })
}
