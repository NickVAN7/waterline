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

  // One Tab stop for the rows, then the focused row's link, then out of the tree (DL-266).
  await page.getByRole('row', { name: /Billing/ }).focus()
  await page.keyboard.press('ArrowDown')
  await expect(page.getByRole('row', { name: /Shipping/ })).toBeFocused()
  await page.keyboard.press('Tab')
  await expect(page.getByRole('link', { name: `${key}-RQ-${shipping.number}` })).toBeFocused()
  await page.keyboard.press('Tab')
  await expect(page.locator('.p-treetable :focus')).toHaveCount(0)

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

// Expand requirement at the ranked view's cap (DL-159, DL-271, DL-272): one top-level requirement
// with 20 children, each with 9 children of 10 children each, less the last leaf, 2,000 in all,
// served to the page as the API would. Opening it shows its 20, then 180 more, then 10 under each
// of the next 30 branches: 500 rows under it, where it stops.
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
  const root = add(null)
  for (let child = 0; child < 20; child++) {
    const a = add(root)
    for (let grandchild = 0; grandchild < 9; grandchild++) {
      const b = add(a)
      for (let leaf = 0; leaf < 10; leaf++) add(b)
    }
  }
  items.pop()
  return { items, truncated: false }
}

test('Expand requirement stops at 500 rows without freezing the page', async ({
  page,
}, testInfo) => {
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
  await expect(titles(page)).toHaveCount(1)
  await titles(page).first().click()
  await page.evaluate(() => ((window as unknown as { longest: { ms: number } }).longest.ms = 0))

  const started = Date.now()
  await page.getByRole('button', { name: 'Expand requirement' }).click()
  await expect(
    page.getByText(
      `Deeper rows under ${key}-RQ-1 stay closed: open them with their arrows or the Right arrow key.`,
    ),
  ).toBeVisible({ timeout: 30_000 })
  const elapsed = Date.now() - started
  await expect(titles(page)).toHaveCount(501)
  const longest = await page.evaluate(
    () => (window as unknown as { longest: { ms: number } }).longest.ms,
  )

  testInfo.annotations.push({
    type: 'measure',
    description: `Expand requirement at 2,000 rows: ${elapsed} ms to the note, longest task ${Math.round(longest)} ms`,
  })
  console.log(
    `[${testInfo.project.name}] Expand requirement at 2,000: ${elapsed} ms, longest task ${Math.round(longest)} ms`,
  )
  // 1 s on the workstation; CI's shared runner is about 2.5 times slower (DL-254).
  expect(longest).toBeLessThan(process.env.CI ? 3000 : 1000)
  // The stopped state, its note showing (ui-reviewer, S2-C18c).
  await expectNoA11yViolations(page)
})

// S2-C17a and TD-88: the create dialog, the first page showing the markdown editor and its
// Preview, checked in a browser in both themes; then its full page, the new requirement's page,
// and editing it (S2-C18a).
test('creating a requirement: the editor and its Preview, its full page, then editing it', async ({
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

  // Expanded into a full page, what was typed comes along (UI-SHL-12).
  await dialog.getByRole('button', { name: 'Open as a full page' }).click()
  await expect(page).toHaveURL(new RegExp(`/acme/projects/${key}/requirements/new$`))
  await expect(page.getByRole('heading', { level: 1, name: 'Create a requirement' })).toBeFocused()
  await expect(page.getByRole('textbox', { name: 'Title', exact: true })).toHaveValue('Refunds')
  await expectNoA11yViolations(page)

  // Created, it lands on the new requirement's page (DL-250).
  await page.getByRole('button', { name: 'Create requirement' }).click()
  const heading = page.getByRole('heading', { level: 1, name: 'Refunds' })
  await expect(heading).toBeFocused()
  await expect(page).toHaveURL(new RegExp(`/acme/projects/${key}/requirements/\\d+$`))

  // Edited in place, with a change note (DL-263).
  await page.getByRole('button', { name: 'Edit', exact: true }).click()
  const title = page.getByRole('textbox', { name: 'Title', exact: true })
  await expect(title).toBeFocused()
  await expectNoA11yViolations(page)
  await title.fill('Refunds and returns')
  await page.getByRole('textbox', { name: 'Change note' }).fill('Returns too')
  await page.getByRole('button', { name: 'Save', exact: true }).click()
  await expect(page.getByRole('heading', { level: 1, name: 'Refunds and returns' })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Edit', exact: true })).toBeFocused()
})

// S2-C18: the requirement's page, opened from the tree, and a stored XSS payload that doesn't run
// (DL-245, UI-MD-1): markdown-it with raw HTML off, then DOMPurify, then the CSP.
test("a requirement's side panel and page: a stored payload doesn't run, and its status changes", async ({
  page,
}, testInfo) => {
  const { user, key } = runFor(testInfo)
  await signIn(page, user)
  const payload = [
    '## Acceptance Criteria',
    '',
    '<script>window.__xss = "script"</script>',
    '<img src=x onerror="window.__xss = \'img\'">',
    '<svg onload="window.__xss = \'svg\'"></svg>',
    "[click](javascript:window.__xss='link')",
    "![x](javascript:window.__xss='image')",
    '1. Works',
  ].join('\n')
  const created = await createRequirement(page, key, 'Stored payload')
  const patched = await page.request.patch(`/api/projects/${key}/requirements/${created.number}`, {
    headers: { Origin: new URL(page.url()).origin },
    data: { version: 1, description_md: payload },
  })
  expect(patched.status()).toBe(200)

  await page.goto(`/acme/projects/${key}/requirements`)
  const listUrl = page.url()
  const idLink = page.getByRole('link', { name: `${key}-RQ-${created.number}` })

  // The ID opens the side panel over the list (UI-SHL-11): its own URL, focus on its title.
  await idLink.focus()
  await page.keyboard.press('Enter')
  const panel = page.getByRole('dialog', { name: 'Stored payload' })
  await expect(panel).toBeVisible()
  await expect(page).toHaveURL(`${listUrl}?open=RQ-${created.number}`)
  await expect(panel.getByRole('heading', { name: 'Stored payload' })).toBeFocused()
  await expect(panel.locator('.markdown')).toContainText('Works')
  expect(await page.evaluate(() => (window as unknown as { __xss?: string }).__xss)).toBeUndefined()
  await expectNoA11yViolations(page)
  await expectOnlyTokenColors(page, 'dialog[open]')

  // A change in the panel, from the keyboard: its menu works over the inert page, and the row
  // under it follows.
  const change = panel.getByRole('button', { name: `Change status of ${key}-RQ-${created.number}` })
  await change.focus()
  await page.keyboard.press('Enter')
  await expect(panel.getByRole('menu')).toBeFocused()
  // Under its button, not where PrimeVue's document coordinates would put it in a fixed panel.
  const button = (await change.boundingBox())!
  const opened = (await panel.getByRole('menu').boundingBox())!
  expect(Math.abs(opened.y - (button.y + button.height))).toBeLessThan(12)
  expect(Math.abs(opened.x - button.x)).toBeLessThan(12)
  await expectNoA11yViolations(page)
  // Esc closes the menu alone, not the panel around it.
  await page.keyboard.press('Escape')
  await expect(panel.getByRole('menu')).toBeHidden()
  await expect(panel).toBeVisible()
  await expect(change).toBeFocused()
  await page.keyboard.press('Enter')
  await panel.getByRole('menu').getByRole('menuitem', { name: 'Deferred' }).click()
  await expect(panel.getByText('Status: Deferred')).toBeVisible()
  await expect(change).toBeFocused()
  await expect(page.getByRole('row', { name: /Stored payload/ })).toContainText('Deferred')

  // Esc in the edit form keeps the panel and what was typed; Cancel ends the edit.
  await panel.getByRole('button', { name: 'Edit' }).click()
  const title = panel.getByLabel('Title')
  await title.fill('Stored payload, edited')
  await page.keyboard.press('Escape')
  await expect(panel).toBeVisible()
  await expect(title).toHaveValue('Stored payload, edited')
  await panel.getByRole('button', { name: 'Cancel' }).click()
  await expect(panel.getByRole('button', { name: 'Edit' })).toBeFocused()

  // Esc closes it as Back would: focus back on the ID, and no history entry left behind.
  await page.keyboard.press('Escape')
  await expect(panel).toBeHidden()
  await expect(page).toHaveURL(listUrl)
  await expect(idLink).toBeFocused()
  await page.goBack()
  await expect(page).not.toHaveURL(listUrl)
  await page.goForward()

  // Browser Back closes it too; Open full page goes to the requirement's page.
  await idLink.click()
  await expect(panel).toBeVisible()
  await page.goBack()
  await expect(panel).toBeHidden()
  await expect(page).toHaveURL(listUrl)
  await idLink.click()
  await panel.getByRole('link', { name: 'Open full page' }).click()

  await expect(page).toHaveURL(new RegExp(`/requirements/${created.number}$`))
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('Stored payload')
  await expect(page.getByRole('heading', { level: 1 })).toBeFocused()
  const description = page.locator('.markdown')
  await expect(description).toContainText('Works')
  // The payloads show as text, or not at all; none runs.
  await expect(description.locator('script, img, svg')).toHaveCount(0)
  await expect(description.getByRole('link', { name: 'click' })).toHaveCount(0)
  expect(await page.evaluate(() => (window as unknown as { __xss?: string }).__xss)).toBeUndefined()
  await expectNoA11yViolations(page)
  await expectFocusNotObscured(page)

  // The status menu from the keyboard: focus goes into the menu, then back to its button.
  const changeOnPage = page.getByRole('button', {
    name: `Change status of ${key}-RQ-${created.number}`,
  })
  await changeOnPage.focus()
  await page.keyboard.press('Enter')
  const menu = page.getByRole('menu')
  await expect(menu).toBeFocused()
  await expectNoA11yViolations(page)
  await menu.getByRole('menuitem', { name: 'In progress' }).click()
  await expect(page.getByText('Status: In progress')).toBeVisible()
  await expect(changeOnPage).toBeFocused()
  await expectNoA11yViolations(page)
})
