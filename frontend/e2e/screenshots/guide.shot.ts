/**
 * The guide's screenshots (DL-343): `wl docs-screenshots` runs these on the end-to-end stack seeded
 * with the manual pass's data (DL-361), so nothing outside the demo data appears. Each shot is
 * saved in its project's theme, as `<name>.webp` in light and `<name>-dark.webp` in dark, in
 * `docs/user-guide/images/`; the guide's pages reference the light one (docs mode adds the dark).
 */
import { writeFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

import { expect, test, type Page } from '@playwright/test'

import { signIn } from '../support/demo'

const IMAGES = fileURLToPath(new URL('../../../docs/user-guide/images/', import.meta.url))

type Shot = { name: string; user: string; path: string; shows?: (page: Page) => Promise<void> }

// About one per guide page (DL-343); each `name` is the file its page shows.
const SHOTS: Shot[] = [
  { name: 'my-work', user: 'ella', path: '/' },
  { name: 'project-settings', user: 'lena', path: '/acme/projects/PORTAL/settings' },
  {
    name: 'requirement-panel',
    user: 'lena',
    path: '/acme/projects/PORTAL/requirements?open=RQ-2',
    shows: (page) =>
      expect(page.getByRole('complementary', { name: 'Requirement PORTAL-RQ-2' })).toBeVisible(),
  },
  { name: 'approval', user: 'ella', path: '/acme/projects/PORTAL/requirements/4' },
  { name: 'project-members', user: 'lena', path: '/acme/projects/PORTAL/members' },
  { name: 'trash', user: 'lena', path: '/acme/projects/PORTAL/trash' },
  { name: 'account', user: 'sam', path: '/account' },
  { name: 'org-overview', user: 'olivia', path: '/acme/overview' },
  { name: 'workspace-users', user: 'wendy', path: '/workspace/users' },
]

/** The PNG Playwright takes, as WebP: Chrome's canvas encodes it, on a blank page (the app's CSP
 * refuses `data:` images). */
async function webp(page: Page, png: Buffer): Promise<Buffer> {
  const blank = await page.context().newPage()
  const encoded = await blank.evaluate(async (base64) => {
    const image = new Image()
    image.src = `data:image/png;base64,${base64}`
    await image.decode()
    const canvas = document.createElement('canvas')
    canvas.width = image.naturalWidth
    canvas.height = image.naturalHeight
    canvas.getContext('2d')!.drawImage(image, 0, 0)
    return canvas.toDataURL('image/webp', 0.9)
  }, png.toString('base64'))
  await blank.close()
  // A browser that can't encode WebP returns PNG instead.
  expect(encoded.startsWith('data:image/webp;base64,')).toBe(true)
  return Buffer.from(encoded.split(',')[1]!, 'base64')
}

for (const shot of SHOTS) {
  test(shot.name, async ({ page }, testInfo) => {
    await signIn(page, shot.user)
    await page.goto(shot.path)
    // The page has settled: its h1 is drawn, and nothing is still loading.
    await expect(page.locator('h1')).toBeVisible()
    await page.waitForLoadState('networkidle')
    await shot.shows?.(page)
    await expect(page.locator('[aria-busy="true"]')).toHaveCount(0)
    // No focus ring in the picture (a panel focuses its title).
    await page.evaluate(() => (document.activeElement as HTMLElement | null)?.blur())

    const suffix = testInfo.project.name === 'dark' ? '-dark' : ''
    writeFileSync(`${IMAGES}${shot.name}${suffix}.webp`, await webp(page, await page.screenshot()))
  })
}
