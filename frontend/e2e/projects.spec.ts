import { expect, test } from '@playwright/test'

import { expectFocusNotObscured, expectNoA11yViolations } from './support/a11y'
import { signIn } from './support/demo'

// `olivia` owns the demo org `acme`, so she may create projects there. Each theme's run creates
// its own project, its key unique to the run (DL-87).

test('a project is created from the project selector, and opens', async ({ page }, testInfo) => {
  const key = `${testInfo.project.name === 'dark' ? 'D' : 'L'}${Date.now().toString(36).slice(-4).toUpperCase()}`
  await signIn(page, 'olivia')
  await page.goto('/acme/projects')

  // The header reads "Waterline", then the org's name beside it, not at the far end (UI-SHL-4,
  // DL-137): a spacer between them would keep their order but push the name away.
  const banner = page.getByRole('banner')
  const appName = (await banner.getByRole('link', { name: 'Waterline' }).boundingBox())!
  const orgName = (await banner.getByText('Acme Manufacturing').boundingBox())!
  expect(orgName.x - (appName.x + appName.width)).toBeLessThan(40)

  // The selector opens by keyboard; New project is in its footer.
  await page.getByRole('button', { name: /Project:/ }).focus()
  await page.keyboard.press('Enter')
  const selector = page.getByRole('dialog', { name: 'Projects' })
  await expect(selector).toHaveAccessibleDescription('Acme Manufacturing')
  // All projects reads as a link apart from the rows; New project lines up with them (DL-137).
  const allProjects = selector.getByRole('link', { name: 'All projects' })
  await expect(allProjects).toHaveCSS('text-decoration-line', 'underline')
  await expect(selector.getByRole('link', { name: /^ERP Rollout/ })).not.toHaveCSS(
    'text-decoration-line',
    'underline',
  )
  const newProject = selector.getByRole('button', { name: 'New project' })
  // Measured once the popover's opening animation has finished: it scales in.
  await page.waitForFunction(() =>
    document.getAnimations().every((animation) => animation.playState !== 'running'),
  )
  // Its text starts where the rows' does: the same left edge and the same inset.
  const rowLink = selector.getByRole('link', { name: /^ERP Rollout/ })
  expect((await newProject.boundingBox())!.x).toBe((await rowLink.boundingBox())!.x)
  const inset = await rowLink.evaluate((element) => getComputedStyle(element).paddingLeft)
  await expect(newProject).toHaveCSS('padding-left', inset)
  await newProject.click()

  const dialog = page.getByRole('dialog', { name: 'Create a project' })
  await expect(dialog.getByRole('textbox', { name: 'Name', exact: true })).toBeFocused()
  // Centered in the viewport (UI-FRM-14, DL-137): the base styles' reset once left it top-left.
  const box = (await dialog.boundingBox())!
  const viewport = page.viewportSize()!
  expect(Math.abs(box.x + box.width / 2 - viewport.width / 2)).toBeLessThanOrEqual(1)
  expect(Math.abs(box.y + box.height / 2 - viewport.height / 2)).toBeLessThanOrEqual(1)
  await dialog.getByRole('textbox', { name: 'Name', exact: true }).fill(`Pilot ${key}`)
  await dialog.getByRole('textbox', { name: 'Key', exact: true }).fill(key.toLowerCase())
  await expect(dialog.getByText('Key is available')).toBeVisible()
  await dialog.getByRole('combobox', { name: 'Type' }).selectOption('erp')
  // The first-admin picker offers an org member and a workspace admin outside the org (DL-152).
  const firstAdmin = dialog.getByRole('combobox', { name: 'First admin' })
  await expect(firstAdmin.getByRole('option', { name: /^Liam Lewis/ })).toBeAttached()
  await expect(firstAdmin.getByRole('option', { name: /^Wendy Walsh/ })).toBeAttached()
  await dialog.getByRole('radio', { name: /^Confidential/ }).check()
  await dialog.getByRole('checkbox', { name: 'Financial' }).check()
  await expectNoA11yViolations(page)
  await dialog.getByRole('button', { name: 'Create project' }).click()

  await expect(page).toHaveURL(`/acme/projects/${key}`)
  await expect(page.getByRole('heading', { level: 1, name: `Pilot ${key}` })).toBeFocused()
  await expect(page.getByText('Lead: Olivia Ortiz')).toBeVisible()
  await expect(page.locator('main header').getByText('Confidential · Financial')).toBeVisible()
  await expectNoA11yViolations(page)
  await expectFocusNotObscured(page)
})

test("the org's projects filter by status and type in the URL", async ({ page }) => {
  await signIn(page, 'olivia')
  await page.goto('/acme/projects')

  const type = page.getByRole('combobox', { name: 'Type' })
  await type.focus()
  await type.selectOption('software')

  await expect(page).toHaveURL('/acme/projects?type=software')
  // A filter change is a query-only navigation: focus stays on the filter (UI-TBL-3).
  await expect(type).toBeFocused()
  await expect(page.getByRole('link', { name: 'Customer Portal' })).toBeVisible()
  await expect(page.getByRole('link', { name: 'ERP Rollout' })).toHaveCount(0)
  await expectNoA11yViolations(page)

  await page.goto('/acme/projects?status=cancelled')
  await expect(
    page.getByRole('heading', { name: 'No projects match Status: Cancelled' }),
  ).toBeVisible()
  await page.getByRole('button', { name: 'Clear filters' }).click()
  await expect(page).toHaveURL('/acme/projects')
  await expect(page.getByRole('combobox', { name: 'Status' })).toBeFocused()
})
