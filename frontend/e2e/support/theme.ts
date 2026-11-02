/**
 * The theme audit (testing strategy, "Accessibility"; ui-design-guide §9): every color a wrapped
 * widget paints must be one of our tokens (UI-TOK-12), so a component colored by its library's
 * own palette fails. Ported from the S2-C0b spike (`docs/spikes/S2-C0b-tree/measure.mjs`).
 */
import { expect, type Page } from '@playwright/test'

/** Fail on any text, background, border, or outline color under `selector` that isn't a token. */
export async function expectOnlyTokenColors(page: Page, selector: string): Promise<void> {
  const unmapped = await page.evaluate((selector) => {
    const probe = document.createElement('div')
    document.body.append(probe)
    const resolve = (value: string) => {
      probe.style.color = ''
      probe.style.color = value
      return getComputedStyle(probe).color
    }
    // Every --color-* custom property declared anywhere, inside @layer and @media blocks too.
    const names: string[] = []
    const walk = (rules: CSSRuleList) => {
      for (const rule of Array.from(rules)) {
        if (rule instanceof CSSStyleRule || 'style' in rule) {
          const style = (rule as CSSStyleRule).style
          names.push(...Array.from(style).filter((name) => name.startsWith('--color-')))
        }
        if ('cssRules' in rule) walk((rule as CSSGroupingRule).cssRules)
      }
    }
    for (const sheet of Array.from(document.styleSheets)) walk(sheet.cssRules)
    const root = getComputedStyle(document.documentElement)
    const allowed = new Set<string>()
    for (const name of new Set(names)) {
      if (root.getPropertyValue(name)) allowed.add(resolve(`var(${name})`))
    }
    // The preset's primary scale mixes the accent toward the page (preset.ts): ours too.
    for (const percent of [6, 12, 24, 40, 70]) {
      allowed.add(resolve(`color-mix(in srgb, var(--color-accent) ${percent}%, var(--color-bg))`))
    }
    probe.remove()

    const found = new Map<string, string>()
    const scope = document.querySelector(selector)!
    for (const element of [scope, ...Array.from(scope.querySelectorAll('*'))]) {
      const style = getComputedStyle(element)
      const sides = ['top', 'right', 'bottom', 'left'] as const
      const checks: [string, string][] = [
        ['color', style.color],
        ['background-color', style.backgroundColor],
        ...sides
          .filter((side) => style.getPropertyValue(`border-${side}-width`) !== '0px')
          .map((side): [string, string] => [
            `border-${side}-color`,
            style.getPropertyValue(`border-${side}-color`),
          ]),
      ]
      if (style.outlineStyle !== 'none') checks.push(['outline-color', style.outlineColor])
      for (const [property, value] of checks) {
        if (value === 'rgba(0, 0, 0, 0)' || allowed.has(value)) continue
        const where = `${element.tagName.toLowerCase()}.${Array.from(element.classList).join('.')}`
        if (!found.has(`${property}: ${value}`)) found.set(`${property}: ${value}`, where)
      }
    }
    return Array.from(found).map(([color, where]) => `${color} (${where.slice(0, 60)})`)
  }, selector)
  expect(unmapped, `colors that aren't tokens:\n${unmapped.join('\n')}`).toEqual([])
}
