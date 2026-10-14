/** The demo dataset the e2e stack is seeded with (`backend/app/demo.py`; developer guide, "Demo
 * data"). */
import { expect, type Page, type TestInfo } from '@playwright/test'

export const DEMO_PASSWORD = 'harbor-demo'

export function email(username: string): string {
  return `${username}@harbor.example`
}

/** One forced-change user per theme run, since the flow clears the flag (DL-87). */
export function forcedChangeUser(testInfo: TestInfo): string {
  return testInfo.project.name === 'dark' ? 'felix' : 'fiona'
}

/** Sign in as a demo user and wait for the page they land on. */
export async function signIn(page: Page, username: string, landing = '/'): Promise<void> {
  await page.goto('/sign-in')
  await page.getByRole('textbox', { name: 'Email', exact: true }).fill(email(username))
  await page.getByRole('textbox', { name: 'Password', exact: true }).fill(DEMO_PASSWORD)
  await page.getByRole('button', { name: 'Sign in' }).click()
  await expect(page).toHaveURL(landing)
}
