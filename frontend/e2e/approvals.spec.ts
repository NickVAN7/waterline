import { expect, test, type Page, type TestInfo } from '@playwright/test'

import { expectFocusNotObscured, expectNoA11yViolations } from './support/a11y'
import { signIn } from './support/demo'
import { expectOnlyTokenColors } from './support/theme'

// Requesting and deciding an approval (build plan Slice 2, "End-to-end tests"; S2-C20, S2-C20a,
// S2-C20b: the approver finds it on My work, and it leaves once decided).
// In Globex's INV, which no other test's requirements use (the tree tests count ERP's and PORTAL's,
// DL-87): its admin requests, and each theme run's own approver decides on its own requirement,
// a viewer in one (a viewer may be an approver, design-doc §6.2).
function runFor(testInfo: TestInfo) {
  return testInfo.project.name === 'dark'
    ? { approver: 'jade', approverName: 'Jade Jensen' }
    : { approver: 'kira', approverName: 'Kira Kowalski' }
}
const ADMIN = 'ivan'
const KEY = 'INV'

async function signOut(page: Page) {
  await page.getByRole('button', { name: /Account menu/ }).click()
  await page.getByRole('menuitem', { name: 'Sign out' }).click()
  await expect(page).toHaveURL(/\/sign-in/)
}

test('an admin requests approval, and the approver reviews and decides', async ({
  page,
}, testInfo) => {
  const { approver, approverName } = runFor(testInfo)
  await signIn(page, ADMIN)
  const created = await page.request.post(`/api/projects/${KEY}/requirements`, {
    headers: { Origin: new URL(page.url()).origin },
    data: { title: 'Refund by card', description_md: 'Refund within **14 days**.' },
  })
  expect(created.status()).toBe(201)
  const { number } = (await created.json()) as { number: number }
  const url = `/globex/projects/${KEY}/requirements/${number}`

  // The admin's side: the dialog opens on the approver list, from the keyboard.
  await page.goto(url)
  const section = page.getByRole('region', { name: 'Approval', exact: true })
  await expect(section).toContainText('No approval has been requested.')
  await section.getByRole('button', { name: 'Request approval' }).focus()
  await page.keyboard.press('Enter')
  const dialog = page.getByRole('dialog')
  await expect(dialog.getByRole('checkbox').first()).toBeFocused()
  await expectNoA11yViolations(page)
  await expectOnlyTokenColors(page, 'dialog[open]')
  await dialog.getByRole('checkbox', { name: approverName }).check()
  await dialog.getByRole('textbox', { name: 'Note' }).fill('Before the release')
  await dialog.getByRole('button', { name: 'Request approval' }).click()
  await expect(dialog).toBeHidden()
  await expect(section).toContainText(/Latest request:\s*Pending/)
  await signOut(page)

  // The approver's side: on My work, then the revision under approval, then the decision.
  await signIn(page, approver)
  const waiting = page.getByRole('region', { name: 'Approvals waiting for you' })
  const item = waiting.locator(`a[href="${url}"]`)
  await expect(item).toHaveText('Refund by card')
  await expectNoA11yViolations(page)
  await expectOnlyTokenColors(page, 'main')
  await item.click()
  await expect(page).toHaveURL(url)
  await expect(section.getByRole('heading', { name: 'Revision 1, under approval' })).toBeVisible()
  await expect(section.locator('strong')).toHaveText('14 days')
  await expectNoA11yViolations(page)
  await expectOnlyTokenColors(page, 'section')
  await expectFocusNotObscured(page)

  // Rejecting without a comment asks first (DL-196); Add a comment goes back to the field.
  await section.getByRole('button', { name: 'Reject' }).focus()
  await page.keyboard.press('Enter')
  const confirm = page.getByRole('dialog', { name: 'Reject without a comment?' })
  await expect(confirm.getByRole('button', { name: 'Add a comment' })).toBeFocused()
  await expectNoA11yViolations(page)
  await page.keyboard.press('Enter')
  const comment = section.getByRole('textbox', { name: 'Comment' })
  await expect(comment).toBeFocused()

  await comment.fill('Matches the card rules.')
  await section.getByRole('button', { name: 'Approve' }).click()
  await expect(section).toContainText(/Latest request:\s*Approved/)
  await expect(section).toContainText('Last approved: revision 1')
  await expect(section).toContainText('Matches the card rules.')
  await expect(section.getByRole('button', { name: 'Approve' })).toHaveCount(0)

  // My work: no longer waiting; the decision stays on the requirement (past decisions left My
  // work, DL-333).
  await page.getByRole('link', { name: 'My work' }).first().click()
  await expect(page.getByRole('heading', { level: 1, name: 'My work' })).toBeVisible()
  await expect(waiting.locator(`a[href="${url}"]`)).toHaveCount(0)
  await expectNoA11yViolations(page)
})
