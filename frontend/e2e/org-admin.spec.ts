import { expect, test } from '@playwright/test'

import { expectFocusNotObscured, expectNoA11yViolations } from './support/a11y'
import { signIn } from './support/demo'

// `olivia` owns the demo org `acme`; `casey` is only a project member there. Nothing here changes
// `acme`'s name or slug, which every other flow relies on.

test('org administration opens from the user menu, by keyboard (UI-SHL-10)', async ({ page }) => {
  await signIn(page, 'olivia')

  await page.getByRole('button', { name: /Account menu/ }).focus()
  await page.keyboard.press('Enter')
  // Focus moves into the menu (frontend/CLAUDE.md, "Overlays"); the arrows reach the item.
  await expect(page.getByRole('menu', { name: 'Account menu' })).toBeFocused()
  const active = page.locator('#user-menu .p-menu-item.p-focus')
  await page.keyboard.press('ArrowDown')
  await expect(active).toHaveText('Account settings')
  await page.keyboard.press('ArrowDown')
  await expect(active).toHaveText('Organization administration')
  await page.keyboard.press('Enter')

  await expect(page).toHaveURL('/acme/members')
  await expect(
    page.getByRole('heading', { level: 1, name: 'Acme Manufacturing members' }),
  ).toBeFocused()
  const nav = page.getByRole('navigation', { name: 'Organization administration' })
  await expect(nav.getByRole('link')).toHaveText(['Members', 'Settings'])
  await expect(nav.getByRole('link', { name: 'Members' })).toHaveAttribute('aria-current', 'page')
  const members = page.getByRole('table', { name: 'Members' })
  await expect(members.getByRole('row', { name: /Olivia/ })).toContainText('Owner')
  await expectNoA11yViolations(page)
  await expectFocusNotObscured(page)
})

test("the org's settings show its name and slug to change", async ({ page }) => {
  await signIn(page, 'olivia')

  await page.goto('/acme/settings')

  await expect(
    page.getByRole('heading', { level: 1, name: 'Acme Manufacturing settings' }),
  ).toBeVisible()
  await expect(page.getByRole('textbox', { name: 'Name', exact: true })).toHaveValue(
    'Acme Manufacturing',
  )
  await expect(page.getByRole('textbox', { name: 'Slug', exact: true })).toHaveValue('acme')
  await expectNoA11yViolations(page)
  await expectFocusNotObscured(page)
})

test("someone who can't manage the org gets the 403 page (UI-FBK-14)", async ({ page }) => {
  await signIn(page, 'casey')

  await page.goto('/acme/members')

  await expect(
    page.getByRole('heading', { level: 1, name: "You can't open this page" }),
  ).toBeVisible()
  await expect(page.getByText('Error 403')).toBeVisible()
  await page.getByRole('button', { name: /Account menu/ }).click()
  await expect(page.getByRole('menuitem', { name: 'Account settings' })).toBeVisible()
  await expect(page.getByRole('menuitem', { name: 'Organization administration' })).toHaveCount(0)
  await expectNoA11yViolations(page)
})
