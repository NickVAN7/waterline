/**
 * The one axe helper for component tests (docs/ui-design-guide.md §9): every view and shared
 * component spec calls `expectNoA11yViolations()` on what it mounted. jsdom has no layout, so
 * contrast and target size come back "incomplete" here (unchecked, not passed); the end-to-end
 * helper (`e2e/support/a11y.ts`) is where they are really checked.
 */
import type { VueWrapper } from '@vue/test-utils'
import type { AxeResults } from 'axe-core'
import { expect } from 'vitest'
import { configureAxe } from 'vitest-axe'

export const A11Y_TAGS = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa']

// `target-size` (WCAG 2.5.8, tag wcag22aa) is off by default in axe-core: opt in. Contrast needs
// rendering jsdom doesn't do (it can only report "incomplete"), so it's left to the end-to-end run.
const axe = configureAxe({
  runOnly: { type: 'tag', values: A11Y_TAGS },
  rules: { 'target-size': { enabled: true }, 'color-contrast': { enabled: false } },
})

/** axe's full results for `target`, which must be attached to the document. */
export function runAxe(target: Element): Promise<AxeResults> {
  return axe(target)
}

/** Fail on any axe violation in what `target` renders (mount it with `attachTo`). */
export async function expectNoA11yViolations(target: Element | VueWrapper): Promise<void> {
  const element = target instanceof Element ? target : (target.element as Element)
  const { violations } = await runAxe(element)
  // One line per violation, naming the rule and where it failed, so a failure reads on its own.
  const found = violations.map(
    (v) => `${v.id}: ${v.help} (${v.nodes.map((n) => n.target.join(' ')).join(', ')})`,
  )
  expect(found, `axe violations:\n${found.join('\n')}`).toEqual([])
}
