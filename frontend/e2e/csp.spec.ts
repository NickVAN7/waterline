import { expect, test, type Page } from '@playwright/test'

import { signIn } from './support/demo'

// The Content-Security-Policy (design-doc §4, DL-142, DL-246): every page carries it, the app
// runs under it without a violation, and a script injected past the sanitizer doesn't run.

test('pages carry a CSP that allows scripts only from our own origin', async ({ page }) => {
  const response = await page.goto('/sign-in')

  const csp = response!.headers()['content-security-policy']
  expect(csp).toContain("script-src 'self'")
  expect(csp).toContain("object-src 'none'")
})

/** Each CSP violation's directive, as the page reports them. */
async function watchViolations(page: Page): Promise<string[]> {
  const violations: string[] = []
  await page.exposeFunction('reportViolation', (directive: string) => violations.push(directive))
  await page.addInitScript(() => {
    document.addEventListener('securitypolicyviolation', (event) =>
      (window as unknown as { reportViolation: (d: string) => void }).reportViolation(
        event.effectiveDirective,
      ),
    )
  })
  return violations
}

test('the signed-in app runs under the CSP, which blocks an injected inline script', async ({
  page,
}) => {
  const violations = await watchViolations(page)

  await signIn(page, 'casey')
  await expect(page.getByRole('region', { name: 'Acme Manufacturing' })).toBeVisible()
  expect(violations).toEqual([])

  const ran = await page.evaluate(() => {
    const script = document.createElement('script')
    script.textContent = 'window.injected = true'
    // An allowed inline script runs as it's appended.
    document.body.append(script)
    return (window as unknown as { injected?: boolean }).injected === true
  })

  expect(ran).toBe(false)
  await expect.poll(() => violations).toEqual(['script-src-elem'])
})

test("a guide page's screenshot loads under the CSP, and only the theme's version shows (DL-343, TD-111)", async ({
  page,
}, testInfo) => {
  const violations = await watchViolations(page)
  await signIn(page, 'casey')
  await page.goto('/docs/trash')

  const theme = testInfo.project.name
  const shown = page.locator('article .markdown img:visible')
  const file = (name: string) => (name === 'dark' ? /\/trash-dark\.webp$/ : /\/trash\.webp$/)
  await expect(page.locator('article .markdown img')).toHaveCount(2)
  await expect(shown).toHaveCount(1)
  await expect(shown).toHaveAttribute('src', file(theme))
  await expect(shown).toHaveAccessibleName(/^A project's Trash/)
  await expect.poll(() => shown.evaluate((img: HTMLImageElement) => img.naturalWidth)).toBe(1440)

  // A theme chosen in Account settings, against the system's, swaps the image too (UI-TOK-2).
  const other = theme === 'dark' ? 'light' : 'dark'
  await page.evaluate((other) => (document.documentElement.dataset.theme = other), other)
  await expect(shown).toHaveAttribute('src', file(other))
  await expect.poll(() => shown.evaluate((img: HTMLImageElement) => img.naturalWidth)).toBe(1440)
  expect(violations).toEqual([])
})
