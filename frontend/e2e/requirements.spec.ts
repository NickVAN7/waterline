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
  // 1 s on the workstation; CI's shared runner is about 2.5 times slower (DL-254).
  expect(longest).toBeLessThan(process.env.CI ? 3000 : 1000)
})

// S2-C17a and TD-88: the create dialog, the first page showing the markdown editor and its
// Preview, checked in a browser in both themes.
test('creating a requirement: the editor and its Preview, then the new row', async ({
  page,
}, testInfo) => {
  const { user, key } = runFor(testInfo)
  await signIn(page, user)
  await page.goto(`/acme/projects/${key}/requirements`)

  await page.getByRole('button', { name: 'New requirement' }).click()
  const dialog = page.getByRole('dialog', { name: 'Create a requirement' })
  await expect(dialog.getByRole('textbox', { name: 'Title', exact: true })).toBeFocused()
  await expectNoA11yViolations(page)
  await expectOnlyTokenColors(page, 'dialog[open] .p-tabs')

  await dialog.getByRole('textbox', { name: 'Title', exact: true }).fill('Refunds')
  await dialog
    .getByRole('textbox', { name: 'Description', exact: true })
    .fill(
      [
        '## Context',
        '',
        'See [the refund policy](https://example.com/policy), and',
        'https://example.com/a/very/long/address/that/keeps/going/without/a/single/break/anywhere',
        '',
        '## Acceptance Criteria',
        '',
        '1. A refund reverses the payment.',
        '',
        '- [ ] Drafted',
        '- [x] Reviewed',
        '',
        '| Case | Amount | Result |',
        '|---|---|---|',
        '| Full | 100 | Refunded |',
      ].join('\n'),
    )
  await dialog.getByRole('tab', { name: 'Preview' }).click()
  const preview = dialog.getByRole('tabpanel')
  await expect(preview.getByRole('link', { name: 'the refund policy' })).toBeVisible()
  await expect(preview.getByRole('img', { name: 'Done', exact: true })).toBeVisible()
  // Contrast, link-in-text-block, and the rest, on the rendered markdown.
  await expectNoA11yViolations(page)
  await expectOnlyTokenColors(page, 'dialog[open] .markdown')

  // Forced colors: the selected tab keeps its bar, in the system's Highlight color (UI-TOK-9).
  // Forced colors turn any other background into an opaque Canvas, so "not transparent" proves
  // nothing: compare with Highlight itself.
  await page.emulateMedia({ forcedColors: 'active' })
  const bar = await dialog.locator('.p-tablist-active-bar').evaluate((el) => {
    const probe = document.createElement('div')
    probe.style.background = 'Highlight'
    document.body.append(probe)
    const highlight = getComputedStyle(probe).backgroundColor
    probe.remove()
    return {
      background: getComputedStyle(el).backgroundColor,
      highlight,
      height: el.getBoundingClientRect().height,
    }
  })
  expect(bar.background).toBe(bar.highlight)
  expect(bar.height).toBeGreaterThanOrEqual(3)
  await page.emulateMedia({ forcedColors: 'none' })

  // At 320 px the long address and the table wrap: no sideways scroll (WCAG 1.4.10). A modal
  // dialog scrolls itself, never the page, so the dialog and its panel are what's measured.
  const size = page.viewportSize()!
  await page.setViewportSize({ width: 320, height: size.height })
  expect(await dialog.evaluate((el) => el.scrollWidth - el.clientWidth)).toBeLessThanOrEqual(0)
  expect(await preview.evaluate((el) => el.scrollWidth - el.clientWidth)).toBeLessThanOrEqual(0)
  await page.setViewportSize(size)

  await dialog.getByRole('button', { name: 'Create requirement' }).click()
  await expect(dialog).toBeHidden()
  const row = page.getByRole('row', { name: /Refunds/ })
  await expect(row).toBeFocused()
  await expect(row).toHaveAttribute('aria-selected', 'true')
})
