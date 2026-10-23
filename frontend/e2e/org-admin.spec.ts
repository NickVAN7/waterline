import { expect, test } from '@playwright/test'

import { expectFocusNotObscured, expectNoA11yViolations } from './support/a11y'
import { signIn } from './support/demo'

// `olivia` owns the demo org `acme`; `casey` is only a project member there. Nothing here changes
// `acme`'s name or slug, which every other flow relies on.

test("org administration opens from the org menu, by keyboard, on the org's overview (UI-SHL-4, UI-SHL-10)", async ({
  page,
}) => {
  await signIn(page, 'olivia')

  // The org's name in the header is the org menu; its admin pages follow the orgs (DL-137).
  await page
    .getByRole('banner')
    .getByRole('button', { name: /Organization:/ })
    .focus()
  await page.keyboard.press('Enter')
  const menu = page.getByRole('dialog', { name: 'Organizations' })
  await expect(menu.getByRole('link')).toHaveText([
    'Acme Manufacturing',
    'Overview',
    'Members',
    'Settings',
  ])
  // Focus lands on the current org (frontend/CLAUDE.md, "Overlays"); Tab reaches its pages.
  await expect(menu.getByRole('link', { name: 'Acme Manufacturing' })).toBeFocused()
  await page.keyboard.press('Tab')
  await expect(menu.getByRole('link', { name: 'Overview' })).toBeFocused()
  await page.keyboard.press('Enter')

  await expect(page).toHaveURL('/acme/overview')
  await expect(
    page.getByRole('heading', { level: 1, name: 'Acme Manufacturing overview' }),
  ).toBeFocused()
  // Each project with its lead, linking to its settings (DL-153, DL-163).
  const projects = page.getByRole('table', { name: 'Projects' })
  await expect(projects.getByRole('row', { name: /ERP Rollout/ })).toContainText('Liam Lewis')
  await expect(projects.getByRole('link', { name: /^ERP Rollout/ })).toHaveAttribute(
    'href',
    '/acme/projects/ERP/settings',
  )
  // The sidebar holds the area's pages, not the project selector (UI-SHL-5).
  const nav = page.getByRole('navigation', { name: 'Organization administration' })
  await expect(nav.getByRole('link')).toHaveText(['Overview', 'Members', 'Settings'])
  await expect(nav.getByRole('link', { name: 'Overview' })).toHaveAttribute('aria-current', 'page')
  await expect(page.getByRole('button', { name: /Project:/ })).toHaveCount(0)
  await expectNoA11yViolations(page)
  await expectFocusNotObscured(page)

  await nav.getByRole('link', { name: 'Members' }).click()
  await expect(page).toHaveURL('/acme/members')
  const members = page.getByRole('table', { name: 'Members' })
  await expect(members.getByRole('row', { name: /Olivia/ })).toContainText('Owner')
  await expectNoA11yViolations(page)
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
  // The org menu offers the orgs only: no admin pages to someone who can't manage it.
  await page
    .getByRole('banner')
    .getByRole('button', { name: /Organization:/ })
    .click()
  const menu = page.getByRole('dialog', { name: 'Organizations' })
  await expect(menu.getByRole('link').first()).toBeVisible()
  await expect(menu.getByRole('link', { name: 'Overview' })).toHaveCount(0)
  await expectNoA11yViolations(page)
})
