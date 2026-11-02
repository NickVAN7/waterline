import { expect, test } from '@playwright/test'

import { signIn } from './support/demo'

// The Content-Security-Policy (design-doc §4, DL-142, DL-246): every page carries it, the app
// runs under it without a violation, and a script injected past the sanitizer doesn't run.

test('pages carry a CSP that allows scripts only from our own origin', async ({ page }) => {
  const response = await page.goto('/sign-in')

  const csp = response!.headers()['content-security-policy']
  expect(csp).toContain("script-src 'self'")
  expect(csp).toContain("object-src 'none'")
})

test('the signed-in app runs under the CSP, which blocks an injected inline script', async ({
  page,
}) => {
  const violations: string[] = []
  await page.exposeFunction('reportViolation', (directive: string) => violations.push(directive))
  await page.addInitScript(() => {
    document.addEventListener('securitypolicyviolation', (event) =>
      (window as unknown as { reportViolation: (d: string) => void }).reportViolation(
        event.effectiveDirective,
      ),
    )
  })

  await signIn(page, 'casey')
  await expect(page.getByRole('region', { name: 'Projects' }).getByRole('link')).toHaveCount(2)
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
