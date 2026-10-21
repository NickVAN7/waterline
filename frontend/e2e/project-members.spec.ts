import { expect, test } from '@playwright/test'

import { expectFocusNotObscured, expectNoA11yViolations } from './support/a11y'
import { signIn } from './support/demo'

// `olivia` owns the demo org `acme`, so she administers its projects (inherited). Each theme's run
// creates its own person (DL-87): added to `PORTAL` by email, given a new role, removed, then
// added back with the picker, since the account stays in the org. Nothing else on `PORTAL` changes.

test("a project's members are added by email and from the picker, changed, removed, and reviewed", async ({
  page,
}, testInfo) => {
  const run = `${testInfo.project.name}${Date.now().toString(36).slice(-5)}`
  const name = `Pat ${run}`
  await signIn(page, 'olivia')
  await page.goto('/acme/projects/PORTAL')
  await page
    .getByRole('navigation', { name: 'Project' })
    .getByRole('link', { name: 'Members' })
    .click()

  await expect(page).toHaveURL('/acme/projects/PORTAL/members')
  await expect(
    page.getByRole('heading', { level: 1, name: 'Customer Portal members' }),
  ).toBeFocused()
  const members = page.getByRole('table', { name: 'Members' })
  await expect(members.getByRole('row', { name: /Ella Evans/ })).toContainText('Admin')
  await expectNoA11yViolations(page)
  await expectFocusNotObscured(page)

  // By email: no account yet, so one is created, its temporary password shown once.
  await page.getByRole('button', { name: 'Add by email' }).click()
  const adder = page.getByRole('dialog', { name: 'Add a person' })
  await adder.getByRole('textbox', { name: 'Email', exact: true }).fill(`${run}@pat.example`)
  await adder.getByRole('button', { name: 'Continue' }).click()
  await adder.getByRole('textbox', { name: 'Name', exact: true }).fill(name)
  await expect(adder.getByRole('textbox', { name: 'Username', exact: true })).not.toHaveValue('')
  await expectNoA11yViolations(page)
  await adder.getByRole('button', { name: 'Create account' }).click()
  await expect(adder.getByText('This password is shown once.')).toBeVisible()
  await adder.getByRole('button', { name: 'Done' }).click()
  // Focus goes back to the opener once the dialog's close event comes (UI-FRM-14).
  await expect(adder).toBeHidden()
  await expect(page.getByRole('button', { name: 'Add by email' })).toBeFocused()
  const row = members.getByRole('row', { name: new RegExp(name) })
  await expect(row).toContainText('Viewer')

  // A new role, from the row's menu, by keyboard.
  await row.getByRole('button', { name: `Actions for ${name}` }).focus()
  await page.keyboard.press('Enter')
  await page.getByRole('menuitem', { name: 'Change role' }).click()
  const changer = page.getByRole('dialog', { name: `Change the role of ${name}` })
  await changer.getByRole('combobox', { name: 'Role' }).selectOption('member')
  await changer.getByRole('button', { name: 'Change role' }).click()
  await expect(row).toContainText('Member')

  // Removed: no option about other projects, since it's one project.
  await row.getByRole('button', { name: `Actions for ${name}` }).click()
  await page.getByRole('menuitem', { name: 'Remove from project' }).click()
  const remover = page.getByRole('dialog', { name: `Remove ${name} from the project?` })
  await expect(remover.getByRole('button', { name: 'Cancel' })).toBeFocused()
  await expect(remover.getByRole('checkbox')).toHaveCount(0)
  await remover.getByRole('button', { name: 'Remove person' }).click()
  await expect(row).toHaveCount(0)

  // Back from the picker: they're still one of the org's members.
  await page.getByRole('button', { name: 'Add member' }).click()
  const picker = page.getByRole('dialog', { name: 'Add a member' })
  const person = picker.getByRole('combobox', { name: 'Person' })
  await expect(person).toBeFocused()
  await person.pressSequentially(run)
  await expect(picker.getByRole('option', { name: new RegExp(name) })).toBeVisible()
  await expectNoA11yViolations(page)
  await picker.getByRole('option', { name: new RegExp(name) }).click()
  await picker.getByRole('button', { name: 'Add member' }).click()
  await expect(picker).toBeHidden()
  await expect(row).toContainText('Viewer')

  // The access review: them by their role, and olivia through the org.
  await page.getByRole('link', { name: 'Access review' }).click()
  await expect(
    page.getByRole('heading', { level: 1, name: 'Customer Portal access review' }),
  ).toBeFocused()
  const review = page.getByRole('table', { name: 'Who reaches the project' })
  await expect(review.getByRole('row', { name: new RegExp(name) })).toContainText('Project viewer')
  await expect(review.getByRole('row', { name: /Olivia Ortiz/ })).toContainText('Org owner')
  await expectNoA11yViolations(page)
  await expectFocusNotObscured(page)
})

test("a project member who isn't its admin reads the list, with nothing to change", async ({
  page,
}) => {
  await signIn(page, 'casey')

  await page.goto('/acme/projects/PORTAL/members')

  await expect(
    page.getByRole('table', { name: 'Members' }).getByRole('row', { name: /Casey Cole/ }),
  ).toBeVisible()
  await expect(page.getByRole('button', { name: 'Add member' })).toHaveCount(0)
  await expect(page.getByRole('link', { name: 'Access review' })).toHaveCount(0)
  await expectNoA11yViolations(page)
  await page.goto('/acme/projects/PORTAL/access')
  await expect(
    page.getByRole('heading', { level: 1, name: "You can't open this page" }),
  ).toBeVisible()
  await expectNoA11yViolations(page)
})
