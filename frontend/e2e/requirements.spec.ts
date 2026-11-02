import { expect, test, type Page, type TestInfo } from '@playwright/test'

import { expectFocusNotObscured, expectNoA11yViolations } from './support/a11y'
import { signIn } from './support/demo'
import { expectOnlyTokenColors } from './support/theme'

// Each theme run works in its own project, as one of its members, so neither sees the other's
// requirements (DL-87): ERP for light (`ben`), PORTAL for dark (`finn`).
function runFor(testInfo: TestInfo) {
  return testInfo.project.name === 'dark'
    ? { user: 'finn', key: 'PORTAL', name: 'Customer Portal' }
    : { user: 'ben', key: 'ERP', name: 'ERP Rollout' }
}

async function createRequirement(page: Page, key: string, title: string, parentId?: string) {
  const response = await page.request.post(`/api/projects/${key}/requirements`, {
    headers: { Origin: new URL(page.url()).origin },
    data: { title, parent_id: parentId ?? null },
  })
  expect(response.status()).toBe(201)
  return (await response.json()) as { id: string; number: number }
}

const titles = (page: Page) => page.locator('[role=treegrid] tbody tr td:first-child')

test('the requirements page: the tree and its moves, in our colors', async ({ page }, testInfo) => {
  const { user, key, name } = runFor(testInfo)
  await signIn(page, user)
  const billing = await createRequirement(page, key, 'Billing')
  await createRequirement(page, key, 'Invoices', billing.id)
  const shipping = await createRequirement(page, key, 'Shipping')
  const returns = await createRequirement(page, key, 'Returns')

  await page.goto(`/acme/projects/${key}`)
  await page
    .getByRole('navigation', { name: 'Project' })
    .getByRole('link', { name: 'Requirements' })
    .click()
  await expect(page.getByRole('heading', { level: 1 })).toHaveText(`${name} requirements`)
  await expect(titles(page)).toHaveText(['Billing', 'Shipping', 'Returns'])
  await expectNoA11yViolations(page)
  await expectOnlyTokenColors(page, '.p-treetable')
  await expectFocusNotObscured(page)

  // Select a row and open the move menu from the keyboard: focus goes into the menu.
  await page.getByRole('row', { name: /Shipping/ }).click()
  const move = page.getByRole('button', { name: `Move ${key}-RQ-${shipping.number}` })
  await move.focus()
  await page.keyboard.press('Enter')
  const menu = page.getByRole('menu')
  await expect(menu).toBeFocused()
  await expectNoA11yViolations(page)
  await expectOnlyTokenColors(page, '.p-treetable')
  await expectOnlyTokenColors(page, '.p-menu')
  await menu.getByRole('menuitem', { name: 'Move to bottom' }).click()
  await expect(titles(page)).toHaveText(['Billing', 'Returns', 'Shipping'])
  await expect(page.getByRole('row', { name: /Shipping/ })).toBeFocused()

  // Move to…: Returns under Billing, which opens to show it.
  await page.getByRole('row', { name: /Returns/ }).click()
  await page.getByRole('button', { name: `Move ${key}-RQ-${returns.number}` }).click()
  await page.getByRole('menuitem', { name: 'Move to…' }).click()
  const dialog = page.getByRole('dialog', { name: `Move ${key}-RQ-${returns.number} to…` })
  await expect(dialog.getByRole('combobox', { name: 'New parent' })).toBeFocused()
  await expectNoA11yViolations(page)
  await dialog
    .getByRole('combobox', { name: 'New parent' })
    .selectOption({ label: `${key}-RQ-${billing.number} Billing` })
  await dialog.getByRole('button', { name: 'Move' }).click()
  await expect(dialog).toBeHidden()
  await expect(titles(page)).toHaveText(['Billing', 'Invoices', 'Returns', 'Shipping'])
  await expect(page.getByRole('row', { name: /Returns/ })).toHaveAttribute('aria-level', '2')
  await expect(page.getByRole('row', { name: /Returns/ })).toBeFocused()
  await expectOnlyTokenColors(page, '.p-treetable')
})

// Expand all at the ranked view's cap (DL-159, DL-175): 20 top-level rows, each with 9 children
// of 10 children each, 2,000 in all, served to the page as the API would.
function treeAtCap() {
  const items: object[] = []
  const id = (n: number) => `0190f0a0-0000-7000-8000-${String(n).padStart(12, '0')}`
  let number = 0
  const add = (parent: string | null) => {
    number += 1
    items.push({
      id: id(number),
      number,
      parent_id: parent,
      title: `Requirement ${number}`,
      status: 'draft',
      priority: 'medium',
      restriction_level: null,
      restriction_categories: [],
      current_revision_id: null,
      approved_revision_id: null,
    })
    return id(number)
  }
  for (let top = 0; top < 20; top++) {
    const a = add(null)
    for (let child = 0; child < 9; child++) {
      const b = add(a)
      for (let leaf = 0; leaf < 10; leaf++) add(b)
    }
  }
  return { items, truncated: false }
}

test('Expand all opens 2,000 rows without freezing the page', async ({ page }, testInfo) => {
  const { user, key } = runFor(testInfo)
  await signIn(page, user)
  await page.route(`**/api/projects/${key}/requirements`, (route) =>
    route.fulfill({ json: treeAtCap() }),
  )
  await page.addInitScript(() => {
    const longest = { ms: 0 }
    ;(window as unknown as { longest: typeof longest }).longest = longest
    new PerformanceObserver((list) => {
      for (const entry of list.getEntries()) longest.ms = Math.max(longest.ms, entry.duration)
    }).observe({ type: 'longtask', buffered: true })
  })
  await page.goto(`/acme/projects/${key}/requirements`)
  await expect(titles(page)).toHaveCount(20)
  await page.evaluate(() => ((window as unknown as { longest: { ms: number } }).longest.ms = 0))

  const started = Date.now()
  await page.getByRole('button', { name: 'Expand all' }).click()
  await expect(titles(page)).toHaveCount(2000, { timeout: 30_000 })
  const elapsed = Date.now() - started
  const longest = await page.evaluate(
    () => (window as unknown as { longest: { ms: number } }).longest.ms,
  )

  testInfo.annotations.push({
    type: 'measure',
    description: `Expand all at 2,000 rows: ${elapsed} ms to the last row, longest task ${Math.round(longest)} ms`,
  })
  console.log(
    `[${testInfo.project.name}] Expand all at 2,000: ${elapsed} ms, longest task ${Math.round(longest)} ms`,
  )
  expect(longest).toBeLessThan(1000)
})
