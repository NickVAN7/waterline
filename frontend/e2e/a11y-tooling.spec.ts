/** The accessibility helpers themselves, each shown able to fail (DL-65, DL-89), on fixtures. */
import { expect, test } from '@playwright/test'

import { expectFocusNotObscured, expectNoA11yViolations } from './support/a11y'

const page = (body: string, style = '') =>
  `<!doctype html><html lang="en"><head><title>Fixture</title><style>${style}</style></head>
   <body><main>${body}</main></body></html>`

test('the axe helper rejects a deliberate violation', async ({ page: browser }) => {
  await browser.setContent(page('<img src="logo.png">'))

  await expect(expectNoA11yViolations(browser)).rejects.toThrow(/image-alt/)
})

test('the axe helper runs target-size and rejects an undersized target', async ({
  page: browser,
}) => {
  await browser.setContent(
    page(
      '<p><button type="button" style="width:12px;height:12px;padding:0">a</button>' +
        '<button type="button" style="width:12px;height:12px;padding:0">b</button></p>',
    ),
  )

  await expect(expectNoA11yViolations(browser)).rejects.toThrow(/target-size/)
})

const links = Array.from({ length: 40 }, (_, i) => `<p><a href="#l${i}">Link ${i}</a></p>`).join('')
const stickyHeader = `
  header { position: sticky; top: 0; height: 56px; background: white; }
  body { margin: 0; }`

test('the focus helper passes when scroll padding clears the sticky header', async ({
  page: browser,
}) => {
  await browser.setContent(
    page(
      `<header><a href="#top">Home</a></header>${links}`,
      `${stickyHeader} html { scroll-padding-top: 72px; }`,
    ),
  )

  await expectFocusNotObscured(browser)
})

test('the focus helper fails when focus lands under the sticky header', async ({
  page: browser,
}) => {
  await browser.setContent(page(`<header><a href="#top">Home</a></header>${links}`, stickyHeader))

  await expect(expectFocusNotObscured(browser)).rejects.toThrow(/drawn under something else/)
})

test('the focus helper keeps going past identical elements', async ({ page: browser }) => {
  // Identical neighbours (a table's Edit buttons) once ended a pass early, skipping the rest;
  // a pair first and a pair last catch a pass that stops on either.
  const edits = '<p><button type="button">Edit</button></p>'.repeat(2)
  await browser.setContent(
    page(`<header><a href="#top">Home</a></header>${edits}${links}${edits}`, stickyHeader),
  )

  await expect(expectFocusNotObscured(browser)).rejects.toThrow(/drawn under something else/)
})
