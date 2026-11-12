import { expect, type Page, test } from '@playwright/test'

import { expectFocusNotObscured, expectNoA11yViolations } from './support/a11y'
import { signIn } from './support/demo'

// `casey` is in both demo orgs, on PORTAL (acme) and INV (globex): the org menu's user.

test('My work lists the projects the user can open, in the shell', async ({ page }) => {
  await signIn(page, 'casey')

  // In two orgs, each its own section, its rows the projects there (DL-329).
  const rows = (org: string) =>
    page.getByRole('region', { name: org }).getByRole('listitem').getByRole('link')
  await expect(rows('Acme Manufacturing')).toHaveText(['Customer Portal'])
  await expect(rows('Globex Retail')).toHaveText(['Inventory System'])
  await expect(page.getByRole('navigation', { name: 'Main' })).toBeVisible()
  await expect(page.getByRole('navigation', { name: 'Project' })).toHaveCount(0)
  await expectNoA11yViolations(page)
  await expectFocusNotObscured(page)
})

// S3-C0f: My work's sections in order, an archived project behind its org's toggle (DL-330,
// DL-349, DL-359). ben is in one org, so its section is just Projects.
test('My work keeps an archived project behind the toggle, starless, marked Archived', async ({
  page,
}) => {
  await signIn(page, 'ben')

  await expect(page.getByRole('heading', { level: 2 })).toHaveText([
    'Favorite projects',
    'Projects',
    'Approvals waiting for you',
  ])
  const projects = page.getByRole('region', { name: 'Projects' })
  await expect(projects.getByRole('link', { name: 'Legacy Cleanup' })).toBeHidden()
  // Its name changes with its state, so it's found by what stays.
  const toggle = projects.getByRole('button', { name: /1 hidden project$/ })
  await expect(toggle).toHaveText('Show 1 hidden project')
  await expect(toggle).toHaveAttribute('aria-expanded', 'false')
  await toggle.focus()
  await page.keyboard.press('Enter')

  await expect(toggle).toHaveText('Hide 1 hidden project')
  await expect(toggle).toHaveAttribute('aria-expanded', 'true')
  await expect(toggle).toBeFocused()
  const legacy = projects.getByRole('listitem').filter({ hasText: 'Legacy Cleanup' })
  await expect(legacy).toContainText('Archived')
  await expect(legacy.getByRole('button', { name: /^Favorite/ })).toHaveCount(0)
  await expect(projects.getByRole('link', { name: /^All \d+ projects?$/ })).toHaveAttribute(
    'href',
    '/acme/projects',
  )
  await expectNoA11yViolations(page)
  await expectFocusNotObscured(page)
})

test('the org menu opens an org, and the project selector one of its projects', async ({
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

test('the org menu and project selector work from the keyboard', async ({ page }) => {
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

test('the user menu opens Documentation, whose pages and sections open from the sidebar and On this page (DL-338 to DL-340)', async ({
  page,
}) => {
  await signIn(page, 'casey')

  await page.getByRole('button', { name: /Account menu/ }).click()
  await page.getByRole('menuitem', { name: 'Documentation' }).click()

  // The guide's pages reached the page through the Compose mount and Vite's allow list (DL-308).
  await expect(page).toHaveURL('/docs')
  await expect(page.getByRole('heading', { level: 1, name: 'Documentation' })).toBeFocused()
  await expect(page).toHaveTitle('Documentation · Waterline')
  await expect(page.getByRole('link', { name: /^Set up a project/ })).toBeVisible()
  const sidebar = page.getByRole('navigation', { name: 'Documentation' })
  await expect(sidebar.getByRole('link', { name: 'Documentation' })).toHaveAttribute(
    'aria-current',
    'page',
  )
  await expectNoA11yViolations(page)

  await sidebar.getByRole('link', { name: 'Requirements' }).click()
  await expect(page).toHaveURL('/docs/requirements')
  await expect(page.getByRole('heading', { level: 1, name: 'Requirements' })).toBeFocused()
  await expect(sidebar.getByRole('link', { name: 'Requirements' })).toHaveAttribute(
    'aria-current',
    'page',
  )
  // Docs mode's callout and keys rendered in the real browser, under the CSP.
  await expect(page.locator('.callout-danger strong')).toHaveText('Warning')
  await expectNoA11yViolations(page)
  // On this page sticks under the header here: nothing Tab reaches sits under either (UI-SHL-3).
  await expectFocusNotObscured(page)

  const contents = page.getByRole('navigation', { name: 'On this page' })
  await contents.getByRole('link', { name: 'Edit a requirement' }).click()
  await expect(page).toHaveURL('/docs/requirements#edit-a-requirement')
  await expect(page.getByRole('heading', { level: 2, name: 'Edit a requirement' })).toBeFocused()
  await expectFocusedHeadingClear(page)

  await page.goBack()
  await expect(page.getByRole('heading', { level: 1, name: 'Requirements' })).toBeFocused()

  // A link in the text opens the other page in the app.
  await page.getByRole('main').getByRole('link', { name: 'Trash', exact: true }).click()
  await expect(page).toHaveURL('/docs/trash')
  await expect(page.getByRole('heading', { level: 1, name: 'Trash' })).toBeFocused()

  await page.goto('/docs/keyboard-and-accessibility#the-requirements-tree')
  await expect(page.getByRole('heading', { level: 2, name: 'The requirements tree' })).toBeFocused()
  await expectFocusedHeadingClear(page)
  await expect(page.locator('main kbd').first()).toHaveText('Tab')
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

test('the theme chosen in account settings applies and stays after a reload (DL-164)', async ({
  page,
}) => {
  await signIn(page, 'casey')
  await page.goto('/account')

  await page.getByRole('radio', { name: 'Dark' }).check()

  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark')
  await expect(page.locator('body')).toHaveCSS('background-color', 'rgb(15, 20, 26)')
  await page.reload()
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark')
  await expect(page.getByRole('radio', { name: 'Dark' })).toBeChecked()
  await expectNoA11yViolations(page)
  // The user menu no longer holds it.
  await page.getByRole('button', { name: /Account menu/ }).click()
  await expect(page.getByRole('menuitemradio')).toHaveCount(0)
})

test('account settings save the profile, and change password is its own page', async ({ page }) => {
  await signIn(page, 'casey')
  await page.getByRole('button', { name: /Account menu/ }).click()
  await page.getByRole('menuitem', { name: 'Account settings' }).click()

  await expect(page.getByRole('menu')).toHaveCount(0)
  await expect(page).toHaveURL('/account')
  await expect(page.getByRole('heading', { level: 1, name: 'Account settings' })).toBeFocused()
  // Saved unchanged, so the shared demo account stays as other tests expect it.
  await page.getByRole('button', { name: 'Save profile' }).click()
  await expect(page.getByText('Profile saved.')).toBeVisible()
  await expectNoA11yViolations(page)

  await page.getByRole('link', { name: 'Change password' }).click()
  await expect(page).toHaveURL('/account/password')
  await expect(page.getByRole('heading', { level: 1, name: 'Change password' })).toBeFocused()
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

/** The focused element (a heading a hash scrolled to) is drawn clear of the sticky header. */
async function expectFocusedHeadingClear(page: Page): Promise<void> {
  const clear = await page.evaluate(() => {
    const element = document.activeElement!
    const box = element.getBoundingClientRect()
    const hit = document.elementFromPoint(box.left + 1, box.top + 1)
    return hit === element || element.contains(hit)
  })
  expect(clear, 'the focused heading is under the sticky header').toBe(true)
}

test('on a wide screen, a list spans the width beside the sidebar; a form and guide text keep their caps (DL-360)', async ({
  page,
}) => {
  await page.setViewportSize({ width: 2400, height: 900 })
  await signIn(page, 'wendy')
  const right = async (selector: string) => {
    const box = (await page.locator(selector).first().boundingBox())!
    return box.x + box.width
  }

  // The users table ends at main's padding, at the window's right edge.
  await page.goto('/workspace/users')
  const main = (await page.locator('main').boundingBox())!
  expect(main.x + main.width).toBe(2400)
  expect(await right('main table')).toBeGreaterThan(2400 - 40)
  expect(await right('main h1 >> xpath=..')).toBeGreaterThan(2400 - 40)

  // Forms stay at --content-narrow (40rem): Account settings' own, and New requirement's, whose
  // cap is on the form itself.
  await page.goto('/account')
  const field = (await page.getByRole('textbox', { name: 'Name', exact: true }).boundingBox())!
  expect(field.width).toBeLessThanOrEqual(640)
  await page.goto('/acme/projects/PORTAL/requirements/new')
  const title = (await page.getByRole('textbox', { name: 'Title', exact: true }).boundingBox())!
  expect(title.width).toBeLessThanOrEqual(640)

  // A guide article's text stays at --content-prose; On this page sits at the right of main.
  await page.goto('/docs/requirements')
  const text = (await page.locator('article .markdown').boundingBox())!
  expect(text.width).toBeLessThan(900)
  expect(await right('nav[aria-label="On this page"]')).toBeGreaterThan(2400 - 40)
})
