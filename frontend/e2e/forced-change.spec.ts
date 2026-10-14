import { expect, test } from '@playwright/test'

import { expectNoA11yViolations } from './support/a11y'
import { DEMO_PASSWORD, email, forcedChangeUser } from './support/demo'

test('a user with a temporary password must change it before anything else', async ({
  page,
}, testInfo) => {
  const username = forcedChangeUser(testInfo)
  const newPassword = `${username}-chose-this-one`

  await page.goto('/sign-in')
  await page.getByRole('textbox', { name: 'Email', exact: true }).fill(email(username))
  await page.getByRole('textbox', { name: 'Password', exact: true }).fill(DEMO_PASSWORD)
  await page.getByRole('button', { name: 'Sign in' }).click()

  await expect(page).toHaveURL('/account/change-password')
  await expect(page.getByRole('heading', { level: 1, name: 'Change your password' })).toBeVisible()
  await expectNoA11yViolations(page)

  // Any other signed-in page sends them back here.
  await page.goto('/')
  await expect(page).toHaveURL('/account/change-password')

  // The server refuses a listed requirement: its line is marked, not a message under the field
  // (DL-94, DL-95).
  await page.getByRole('textbox', { name: 'Current password', exact: true }).fill(DEMO_PASSWORD)
  await page.getByRole('textbox', { name: 'New password', exact: true }).fill(DEMO_PASSWORD)
  await page.getByRole('button', { name: 'Change password' }).click()
  await expect(page.getByRole('textbox', { name: 'New password', exact: true })).toBeFocused()
  await expect(page.getByRole('textbox', { name: 'New password', exact: true })).toHaveAttribute(
    'aria-invalid',
    'true',
  )
  await expect(page.locator('#new_password-requirements li').last()).toHaveText(
    /^\s*Not met:\s*Not your current password\s*$/,
  )
  await expect(page.getByText('Choose a password different from the current one.')).toHaveCount(0)
  await expectNoA11yViolations(page)

  await page.getByRole('textbox', { name: 'New password', exact: true }).fill(newPassword)
  await page.getByRole('button', { name: 'Change password' }).click()
  await expect(page).toHaveURL('/')
  await expect(page.getByRole('heading', { level: 1, name: 'My work' })).toBeVisible()

  // The new password is the one that works now.
  await page.getByRole('button', { name: /Account menu/ }).click()
  await page.getByRole('menuitem', { name: 'Sign out' }).click()
  await page.getByRole('textbox', { name: 'Email', exact: true }).fill(email(username))
  await page.getByRole('textbox', { name: 'Password', exact: true }).fill(newPassword)
  await page.getByRole('button', { name: 'Sign in' }).click()
  await expect(page).toHaveURL('/')
})
