/**
 * The end-to-end accessibility helpers (docs/ui-design-guide.md §9). Here, unlike jsdom, there is
 * layout, so contrast and target size are really checked.
 */
import AxeBuilder from '@axe-core/playwright'
import { expect, type Page } from '@playwright/test'

export const A11Y_TAGS = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa']

/** Fail on any axe violation on the page once it's still: an overlay mid-fade has partial opacity,
 * which axe would report as low contrast. */
export async function expectNoA11yViolations(page: Page): Promise<void> {
  await page.waitForFunction(() =>
    document.getAnimations().every((animation) => animation.playState !== 'running'),
  )
  // `options` first: `withTags` adds to them. `target-size` is off by default in axe-core.
  const { violations } = await new AxeBuilder({ page })
    .options({ rules: { 'target-size': { enabled: true } } })
    .withTags(A11Y_TAGS)
    .analyze()
  const found = violations.map(
    (v) => `${v.id}: ${v.help} (${v.nodes.map((n) => n.target.join(' ')).join(', ')})`,
  )
  expect(found, `axe violations:\n${found.join('\n')}`).toEqual([])
}

/**
 * Focus Not Obscured (WCAG 2.4.11), which axe doesn't automate: Tab forward through the page and
 * then back, and after each press the element at the centre of the focused element's box must be
 * that element or inside it, never a sticky header or toast drawn over it. Going back matters:
 * scrolling up is what puts an element at the top edge, under a sticky header.
 */
export async function expectFocusNotObscured(page: Page, maxPresses = 100): Promise<void> {
  const covered: string[] = []
  for (const key of ['Tab', 'Shift+Tab']) {
    for (let press = 0; press < maxPresses; press += 1) {
      await page.keyboard.press(key)
      const focus = await page.evaluate(() => {
        const element = document.activeElement
        if (!element || element === document.body) return undefined
        const box = element.getBoundingClientRect()
        const hit = document.elementFromPoint(box.left + box.width / 2, box.top + box.height / 2)
        const name = element.outerHTML.slice(0, 80)
        return { name, clear: hit !== null && (hit === element || element.contains(hit)) }
      })
      // Past the last element focus goes to the browser's UI (body here), which ends the pass.
      if (!focus) break
      if (!focus.clear) covered.push(`${key}: ${focus.name}`)
    }
  }
  expect(covered, 'focused elements drawn under something else').toEqual([])
}
