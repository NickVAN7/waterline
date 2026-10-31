import { expect, test } from '@playwright/test'

import { expectFocusNotObscured, expectNoA11yViolations } from './support/a11y'
import { signIn } from './support/demo'

// `wendy` is the demo workspace's admin: she sees every workspace page, the settings read-only
// (they're changed by owners and system admins, DL-45).

test('workspace administration opens from the user menu, by keyboard (UI-SHL-10)', async ({
  page,
}) => {
  await signIn(page, 'wendy')

  const menuButton = page.getByRole('button', { name: /Account menu/ })
  await menuButton.focus()
  await page.keyboard.press('Enter')
  const item = page.getByRole('menuitem', { name: 'Administration', exact: true })
  await expect(item).toBeVisible()
  await item.click()

  await expect(page).toHaveURL('/workspace/staff')
  await expect(page.getByRole('heading', { level: 1, name: 'Workspace staff' })).toBeFocused()
  const nav = page.getByRole('navigation', { name: 'Workspace administration' })
  await expect(nav.getByRole('link')).toHaveText(['Staff', 'Organizations', 'Users', 'Settings'])
  await expect(nav.getByRole('link', { name: 'Staff' })).toHaveAttribute('aria-current', 'page')
  await expectNoA11yViolations(page)
  await expectFocusNotObscured(page)
})

test('the organizations and users pages list the workspace', async ({ page }) => {
  await signIn(page, 'wendy')

  await page.goto('/workspace/orgs')
  await expect(page.getByRole('heading', { level: 1, name: 'Organizations' })).toBeVisible()
  const orgs = page.getByRole('table', { name: 'Organizations in the workspace' })
  await expect(orgs.getByRole('link')).toHaveText(['Acme Manufacturing', 'Globex Retail'])
  await expectNoA11yViolations(page)

  await page.goto('/workspace/users')
  const users = page.getByRole('table', { name: 'Users in the workspace' })
  await expect(users.getByRole('row', { name: /Admin/ }).first()).toBeVisible()
  await expectNoA11yViolations(page)
  await expectFocusNotObscured(page)
})

test("a person's access review opens from their row", async ({ page }) => {
  await signIn(page, 'wendy')
  await page.goto('/workspace/users')

  // Casey Cole, early in the list by name: on PORTAL (acme) and INV (globex).
  // The row's menu, opened from the keyboard: focus moves into it (frontend/CLAUDE.md, "Overlays").
  await page.getByRole('button', { name: 'Actions for Casey Cole' }).focus()
  await page.keyboard.press('Enter')
  const menu = page.getByRole('menu', { name: 'Actions for Casey Cole' })
  await expect(menu).toBeFocused()
  await expectNoA11yViolations(page)
  await menu.getByRole('menuitem', { name: 'Access review' }).click()

  await expect(page).toHaveURL(/\/workspace\/users\/[^/]+\/access$/)
  await expect(
    page.getByRole('heading', { level: 1, name: 'Access review: Casey Cole' }),
  ).toBeFocused()
  const projects = page.getByRole('table', { name: 'Projects' })
  await expect(projects.getByRole('row')).toHaveCount(3) // the header, PORTAL, and INV
  await expectNoA11yViolations(page)
})

test('a new staff member is created email first, the password shown once', async ({
  page,
}, testInfo) => {
  // Unique to the run, so each theme's run creates its own (DL-87).
  const handle = `e2e-${testInfo.project.name}-${Date.now()}`
  await signIn(page, 'wendy')
  await page.goto('/workspace/staff')

  await page.getByRole('button', { name: 'Add person' }).click()
  const dialog = page.getByRole('dialog', { name: 'Add a person' })
  await expect(dialog.getByRole('textbox', { name: 'Email', exact: true })).toBeFocused()
  await dialog.getByRole('textbox', { name: 'Email', exact: true }).fill(`${handle}@harbor.example`)
  await dialog.getByRole('button', { name: 'Continue' }).click()

  await expect(dialog.getByText('No account has this email yet.')).toBeVisible()
  await dialog.getByRole('textbox', { name: 'Name', exact: true }).fill('Ellie Two')
  await dialog.getByRole('textbox', { name: 'Username', exact: true }).fill(handle)
  await expectNoA11yViolations(page)
  await dialog.getByRole('button', { name: 'Create account' }).click()

  await expect(dialog.getByText('This password is shown once.')).toBeVisible()
  await expect(dialog.getByRole('button', { name: 'Done' })).toBeFocused()
  await dialog.getByRole('button', { name: 'Done' }).click()

  await expect(dialog).toBeHidden()
  await expect(page.getByRole('button', { name: 'Add person' })).toBeFocused()
  await expect(page.getByText("Ellie Two added to the workspace's staff.")).toBeVisible()
  await expect(page.getByRole('cell', { name: `${handle}@harbor.example` })).toBeVisible()
})

test('someone not on the staff gets the 403 page, saying who to ask (UI-FBK-14)', async ({
  page,
}) => {
  await signIn(page, 'casey')

  await page.goto('/workspace/staff')

  // A direct load: the title names the page; focus stays put on a first load (UI-SHL-9).
  const heading = page.getByRole('heading', { level: 1, name: "You can't open this page" })
  await expect(heading).toBeVisible()
  await expect(page).toHaveTitle("You can't open this page · Waterline")
  await expect(page.getByText('Error 403')).toBeVisible()
  await expect(page.getByText('Ask one of them if you need it.')).toBeVisible()
  await page.getByRole('button', { name: /Account menu/ }).click()
  await expect(page.getByRole('menuitem', { name: 'Account settings' })).toBeVisible()
  await expect(page.getByRole('menuitem', { name: 'Administration', exact: true })).toHaveCount(0)
  await expectNoA11yViolations(page)
  await expectFocusNotObscured(page)
})
