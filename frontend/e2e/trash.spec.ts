import { expect, test } from '@playwright/test'

import { expectFocusNotObscured, expectNoA11yViolations } from './support/a11y'
import { signIn } from './support/demo'
import { expectOnlyTokenColors } from './support/theme'

// Deleting and restoring a tree (build plan Slice 2, "End-to-end tests"; S2-C21, design-doc §9,
// DL-287 to DL-291). In Globex's INV, which the tree tests don't count (DL-87); each theme run
// deletes its own pair, named by the run, so the two never meet in the trash.
const KEY = 'INV'

test('an admin deletes a requirement with its child, and restores both from Trash', async ({
  page,
}, testInfo) => {
  await signIn(page, 'ivan')
  const origin = { Origin: new URL(page.url()).origin }
  const stamp = `${testInfo.project.name} ${Date.now()}`
  const create = async (title: string, parent_id?: string) => {
    const response = await page.request.post(`/api/projects/${KEY}/requirements`, {
      headers: origin,
      data: { title, description_md: '', ...(parent_id ? { parent_id } : {}) },
    })
    expect(response.status()).toBe(201)
    return (await response.json()) as { id: string; number: number }
  }
  const parent = await create(`Card refunds ${stamp}`)
  const child = await create(`Partial refunds ${stamp}`, parent.id)
  const parentId = `${KEY}-RQ-${parent.number}`

  // Delete, from the keyboard: the dialog starts on Cancel, and asks about the child.
  await page.goto(`/globex/projects/${KEY}/requirements/${parent.number}`)
  await page.getByRole('button', { name: 'Delete', exact: true }).focus()
  await page.keyboard.press('Enter')
  const dialog = page.getByRole('dialog', { name: `Delete ${parentId}?` })
  await expect(dialog.getByRole('button', { name: 'Cancel' })).toBeFocused()
  await dialog.getByRole('radio', { name: 'Delete them too' }).check()
  await expect(dialog).toContainText(
    'Any pending approval request on it and on its children is cancelled.',
  )
  await expectNoA11yViolations(page)
  await expectOnlyTokenColors(page, 'dialog[open]')
  await dialog.getByRole('button', { name: 'Delete requirement' }).click()

  // The tree, saying where it went, focus on its h1.
  await expect(page).toHaveURL(`/globex/projects/${KEY}/requirements`)
  await expect(page.getByRole('heading', { level: 1 })).toBeFocused()
  await expect(page.getByText(`${parentId} moved to Trash.`)).toBeVisible()
  // Said once: the entry no longer carries it, so a reload of the tree doesn't say it again.
  expect(await page.evaluate(() => (history.state as { deleted?: string }).deleted)).toBeUndefined()
  const gone = await page.request.get(`/api/projects/${KEY}/requirements/${child.number}`)
  expect(gone.status()).toBe(404)

  // Trash, last in the project's navigation, lists both; Restore brings both back.
  await page
    .getByRole('navigation', { name: 'Project' })
    .getByRole('link', { name: 'Trash' })
    .click()
  await expect(page).toHaveURL(`/globex/projects/${KEY}/trash`)
  const rows = page.getByRole('row').filter({ hasText: stamp })
  await expect(rows).toHaveCount(2)
  await expect(
    page.getByRole('navigation', { name: 'Project' }).getByRole('link').last(),
  ).toHaveText('Trash')
  await expectNoA11yViolations(page)
  await expectOnlyTokenColors(page, 'main')
  await page.getByRole('button', { name: `Restore ${parentId}` }).click()
  await expect(page.getByText(`Restored ${parentId}.`)).toBeVisible()
  await expect(rows).toHaveCount(0)
  await expectFocusNotObscured(page)

  await page.getByRole('link', { name: `Open ${parentId}` }).click()
  await expect(page.getByRole('heading', { level: 1 })).toHaveText(`Card refunds ${stamp}`)
  const back = await page.request.get(`/api/projects/${KEY}/requirements/${child.number}`)
  expect(((await back.json()) as { parent_id: string }).parent_id).toBe(parent.id)
})
