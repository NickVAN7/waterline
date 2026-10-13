/** The demo dataset the e2e stack is seeded with (`backend/app/demo.py`; developer guide, "Demo
 * data"). */
import type { TestInfo } from '@playwright/test'

export const DEMO_PASSWORD = 'harbor-demo'

export function email(username: string): string {
  return `${username}@harbor.example`
}

/** One forced-change user per theme run, since the flow clears the flag (DL-87). */
export function forcedChangeUser(testInfo: TestInfo): string {
  return testInfo.project.name === 'dark' ? 'felix' : 'fiona'
}
