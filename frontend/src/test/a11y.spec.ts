import { afterEach, describe, expect, it } from 'vitest'

import { expectNoA11yViolations, runAxe } from './a11y'

function fixture(html: string): HTMLElement {
  const element = document.createElement('div')
  element.innerHTML = html
  document.body.append(element)
  return element
}

afterEach(() => {
  document.body.innerHTML = ''
})

describe('expectNoA11yViolations', () => {
  it('rejects a deliberate violation (an image with no text alternative)', async () => {
    const element = fixture('<img src="logo.png">')

    await expect(expectNoA11yViolations(element)).rejects.toThrow(/image-alt/)
  })

  it('passes accessible markup', async () => {
    await expect(
      expectNoA11yViolations(fixture('<img src="logo.png" alt="Waterline">')),
    ).resolves.toBeUndefined()
  })

  it('runs the target-size rule, which axe-core leaves off by default', async () => {
    const results = await runAxe(fixture('<button type="button">x</button>'))

    const ran = [...results.violations, ...results.passes, ...results.incomplete].map((r) => r.id)
    expect(ran).toContain('target-size')
  })
})
