import { expect, test } from '@playwright/test'

import { expectNoA11yViolations } from './support/a11y'
import { DEMO_PASSWORD, email } from './support/demo'

test('signing in lands on My work, and signing out returns to sign-in', async ({ page }) => {
  await page.goto('/')
  await expect(page).toHaveURL('/sign-in')
  await expect(page.getByRole('heading', { level: 1, name: 'Sign in' })).toBeVisible()
  await expectNoA11yViolations(page)

  await page.getByRole('textbox', { name: 'Email', exact: true }).fill(email('casey'))
  await page.getByRole('textbox', { name: 'Password', exact: true }).fill(DEMO_PASSWORD)
  await page.getByRole('button', { name: 'Sign in' }).click()

  await expect(page).toHaveURL('/')
  await expect(page.getByRole('heading', { level: 1, name: 'My work' })).toBeVisible()
  await expect(page).toHaveTitle('My work · Waterline')
  // PrimeVue checks its license key offline as the app starts; without a valid one it adds this
  // notice to the page (DL-135). By now, signed in and on a page, the check is long done.
  await expect(page.locator('#p-license-host')).toHaveCount(0)
  await expectNoA11yViolations(page)

  await page.getByRole('button', { name: /Account menu/ }).click()
  await page.getByRole('menuitem', { name: 'Sign out' }).click()
  await expect(page).toHaveURL('/sign-in')
  await page.goto('/')
  await expect(page).toHaveURL('/sign-in')
})

test('a wrong password is refused with a message, and the email stays', async ({ page }) => {
  await page.goto('/sign-in')
  await page.getByRole('textbox', { name: 'Email', exact: true }).fill(email('casey'))
  await page.getByRole('textbox', { name: 'Password', exact: true }).fill('not-the-password')
  await page.getByRole('button', { name: 'Sign in' }).click()

  const alert = page.getByRole('alert')
  await expect(alert).toHaveText(/The email or password is incorrect\./)
  await expect(alert).toBeFocused()
  await expect(page.getByRole('textbox', { name: 'Email', exact: true })).toHaveValue(
    email('casey'),
  )
  await expect(page).toHaveURL('/sign-in')
  await expectNoA11yViolations(page)
})

test('an empty form marks both fields and focuses the first', async ({ page }) => {
  await page.goto('/sign-in')
  await page.getByRole('button', { name: 'Sign in' }).click()

  await expect(page.getByRole('textbox', { name: 'Email', exact: true })).toBeFocused()
  await expect(page.getByRole('textbox', { name: 'Email', exact: true })).toHaveAttribute(
    'aria-invalid',
    'true',
  )
  await expect(page.getByText('This is required.')).toHaveCount(2)
  await expectNoA11yViolations(page)
})

test('a deep link signs in to where it was going', async ({ page }) => {
  await page.goto('/no-such-page')
  await expect(page).toHaveURL('/sign-in?next=/no-such-page')

  await page.getByRole('textbox', { name: 'Email', exact: true }).fill(email('casey'))
  await page.getByRole('textbox', { name: 'Password', exact: true }).fill(DEMO_PASSWORD)
  await page.getByRole('button', { name: 'Sign in' }).click()

  await expect(page).toHaveURL('/no-such-page')
  await expect(page.getByRole('heading', { level: 1, name: 'Page not found' })).toBeFocused()
  await expectNoA11yViolations(page)
})

test('the status page is open without signing in', async ({ page }) => {
  await page.goto('/status')

  await expect(page.getByRole('heading', { level: 1, name: 'System status' })).toBeVisible()
  await expect(page.getByText('The API and database are up.')).toBeVisible()
  await expectNoA11yViolations(page)
})

// Without this, a lost `color-scheme` would run both projects in the light theme unnoticed.
const PAGE_BACKGROUND: Record<string, string> = {
  light: 'rgb(255, 255, 255)',
  dark: 'rgb(15, 20, 26)',
}

test('each run renders in its own theme', async ({ page }, testInfo) => {
  await page.goto('/sign-in')

  await expect(page.locator('body')).toHaveCSS(
    'background-color',
    PAGE_BACKGROUND[testInfo.project.name] ?? '',
  )
})
