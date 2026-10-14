import { expect, test } from '@playwright/test'

import { expectFocusNotObscured, expectNoA11yViolations } from './support/a11y'
import { signIn } from './support/demo'

// `casey` is in both demo orgs, on PORTAL (acme) and INV (globex): the org switcher's user.

test('My work lists the projects the user can open, in the shell', async ({ page }) => {
  await signIn(page, 'casey')

  const projects = page.getByRole('region', { name: 'Projects' })
  await expect(projects.getByRole('link')).toHaveText(['Customer Portal', 'Inventory System'])
  await expect(page.getByRole('navigation', { name: 'Main' })).toBeVisible()
  await expect(page.getByRole('navigation', { name: 'Project' })).toHaveCount(0)
  await expectNoA11yViolations(page)
  await expectFocusNotObscured(page)
})

test('the org switcher opens an org, and the project selector one of its projects', async ({
  page,
}) => {
  await signIn(page, 'casey')

  await page.getByRole('button', { name: /Organization:/ }).click()
  const orgs = page.getByRole('dialog', { name: 'Organizations' })
  await expect(orgs.getByRole('link')).toHaveText(['Acme Manufacturing', 'Globex Retail'])
  await expectNoA11yViolations(page)
  await orgs.getByRole('link', { name: 'Globex Retail' }).click()

  await expect(page).toHaveURL('/globex/projects')
  await expect(
    page.getByRole('heading', { level: 1, name: 'Globex Retail projects' }),
  ).toBeFocused()
  await expect(page.getByRole('button', { name: /Organization:/ })).toHaveText(/Globex Retail/)
  await expectNoA11yViolations(page)
  await expectFocusNotObscured(page)

  await page.getByRole('button', { name: /Project:/ }).click()
  const selector = page.getByRole('dialog', { name: 'Projects' })
  await expect(selector.getByRole('link', { name: 'All projects' })).toBeVisible()
  await expectNoA11yViolations(page)
  await selector.getByRole('link', { name: /Inventory System/ }).click()

  await expect(page).toHaveURL('/globex/projects/INV')
  await expect(page.getByRole('heading', { level: 1, name: 'Inventory System' })).toBeFocused()
  await expect(page).toHaveTitle('Inventory System · Waterline')
  const projectNav = page.getByRole('navigation', { name: 'Project' })
  await expect(projectNav.getByRole('link', { name: 'Home' })).toHaveAttribute(
    'aria-current',
    'page',
  )
  await expect(page.getByRole('button', { name: /Project:/ })).toHaveText(/Inventory System/)
  await expectNoA11yViolations(page)
  await expectFocusNotObscured(page)
})

test('the org switcher and project selector work from the keyboard', async ({ page }) => {
  await signIn(page, 'casey')

  const switcher = page.getByRole('button', { name: /Organization:/ })
  await switcher.focus()
  await page.keyboard.press('Enter')
  const orgs = page.getByRole('dialog', { name: 'Organizations' })
  await expect(orgs.getByRole('link', { name: 'Acme Manufacturing' })).toBeFocused()
  await page.keyboard.press('Escape')
  await expect(orgs).toHaveCount(0)
  await expect(switcher).toBeFocused()

  const selector = page.getByRole('button', { name: /Project:/ })
  await selector.focus()
  await page.keyboard.press('Enter')
  const projects = page.getByRole('dialog', { name: 'Projects' })
  // Focus lands on the first project once the list has loaded, not on All projects.
  await expect(projects.getByRole('link', { name: /Customer Portal/ })).toBeFocused()
  await page.keyboard.press('Escape')
  await expect(selector).toBeFocused()
})

test('the user menu works from the keyboard, with a visible focus ring', async ({ page }) => {
  await signIn(page, 'casey')

  const button = page.getByRole('button', { name: /Account menu/ })
  await button.focus()
  await page.keyboard.press('Enter')
  const menu = page.getByRole('menu', { name: 'Account menu' })
  await expect(menu).toBeVisible()
  await page.keyboard.press('ArrowDown')

  // PrimeVue marks the active item with `.p-focus`; it carries our ring, not just a tint.
  const focused = page.locator('.p-menu-item.p-focus > .p-menu-item-content')
  await expect(focused).toHaveCount(1)
  await expect(focused).not.toHaveCSS('outline-style', 'none')
  await expectNoA11yViolations(page)

  await page.keyboard.press('Escape')
  await expect(menu).toHaveCount(0)
  await expect(button).toBeFocused()
})

test("a project's lowercase key is replaced with its own", async ({ page }) => {
  await signIn(page, 'casey')

  await page.goto('/acme/projects/portal')

  await expect(page).toHaveURL('/acme/projects/PORTAL')
  await expect(page.getByRole('heading', { level: 1, name: 'Customer Portal' })).toBeVisible()
})

test("a project the user isn't on is not found, the same as one that doesn't exist", async ({
  page,
}) => {
  await signIn(page, 'casey')

  // Everything the page shows is the same for both, so it can't tell anyone ERP exists.
  const notFound = page.getByRole('heading', { level: 1, name: 'Page not found' })
  await page.goto('/acme/projects/ERP')
  await expect(notFound).toBeVisible()
  const hidden = { title: await page.title(), main: await page.locator('main').innerText() }
  await page.goto('/acme/projects/NOPE')
  await expect(notFound).toBeVisible()
  const missing = { title: await page.title(), main: await page.locator('main').innerText() }
  expect(hidden).toEqual(missing)
  await expectNoA11yViolations(page)
})

test('the theme chosen in the user menu applies and stays after a reload', async ({ page }) => {
  await signIn(page, 'casey')

  await page.getByRole('button', { name: /Account menu/ }).click()
  await expectNoA11yViolations(page)
  await page.getByRole('menuitemradio', { name: 'Dark theme' }).click()

  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark')
  await expect(page.locator('body')).toHaveCSS('background-color', 'rgb(15, 20, 26)')
  await page.reload()
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark')
  await page.getByRole('button', { name: /Account menu/ }).click()
  await expect(page.getByRole('menuitemradio', { name: 'Dark theme' })).toHaveAttribute(
    'aria-checked',
    'true',
  )
})

test('account settings save the profile and check a new password as it is typed', async ({
  page,
}) => {
  await signIn(page, 'casey')
  await page.getByRole('button', { name: /Account menu/ }).click()
  await page.getByRole('menuitem', { name: 'Account settings' }).click()

  await expect(page.getByRole('menu')).toHaveCount(0)
  await expect(page).toHaveURL('/account')
  await expect(page.getByRole('heading', { level: 1, name: 'Account settings' })).toBeFocused()
  // Saved unchanged, so the shared demo account stays as other tests expect it.
  await page.getByRole('button', { name: 'Save profile' }).click()
  await expect(page.getByText('Profile saved.')).toBeVisible()

  const requirements = page.locator('#new_password-requirements li')
  await expect(requirements.first()).toHaveText(/Not met:\s*At least 8 characters/)
  await page.getByRole('textbox', { name: 'New password', exact: true }).fill('a long passphrase')
  await expect(requirements.first()).toHaveText(/Met:\s*At least 8 characters/)
  await expectNoA11yViolations(page)
  await expectFocusNotObscured(page)
})

test('a user with no memberships left sees the no-access page', async ({ page }) => {
  await signIn(page, 'nora', '/account/no-access')

  await expect(page.getByRole('heading', { level: 1, name: 'No access' })).toBeVisible()
  await expectNoA11yViolations(page)
})

test('below 48rem the sidebar is behind the Menu button', async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 800 })
  await signIn(page, 'casey')

  const menu = page.getByRole('button', { name: 'Menu', exact: true })
  await expect(page.getByRole('navigation', { name: 'Main' })).toBeHidden()
  await menu.click()

  await expect(menu).toHaveAttribute('aria-expanded', 'true')
  await expect(page.getByRole('navigation', { name: 'Main' })).toBeVisible()
  await expectNoA11yViolations(page)
  await expectFocusNotObscured(page)
})

test('the shell reflows to 320 CSS px with no horizontal scroll', async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 800 })
  await signIn(page, 'casey')
  await page.getByRole('button', { name: 'Menu', exact: true }).click()
  const overflow = () =>
    page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)

  expect(await overflow()).toBe(0)
  await page.goto('/account')
  await expect(page.getByRole('heading', { level: 1, name: 'Account settings' })).toBeVisible()
  expect(await overflow()).toBe(0)
})

test('focus is never under the sticky header on a page that scrolls', async ({ page }) => {
  // Above 40rem (sticky header) and short, so account settings scrolls under it.
  await page.setViewportSize({ width: 900, height: 400 })
  await signIn(page, 'casey')
  await page.goto('/account')
  await expect(page.getByRole('heading', { level: 1, name: 'Account settings' })).toBeVisible()

  await expectFocusNotObscured(page)
})
