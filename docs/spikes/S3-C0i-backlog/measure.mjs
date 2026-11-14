// Measures both widgets against DL-344's checklist and writes results.json. Run from this folder
// with the dev server up (`npm run dev`): `node measure.mjs`. BASE=http://localhost:5196/
// OUT=results-build.json measures the production build (`npx vite build && npx vite preview
// --port 5196`).
import { writeFileSync } from 'node:fs'

import AxeBuilder from '@axe-core/playwright'
import { chromium } from '@playwright/test'

const BASE = process.env.BASE ?? 'http://localhost:5197/'
const browser = await chromium.launch()
const results = {}
const GRID = '[role=grid], [role=table]'

async function open(widget, query = '') {
  const context = await browser.newContext({ viewport: { width: 1280, height: 900 } })
  const page = await context.newPage()
  const errors = []
  page.on('pageerror', (e) => errors.push(e.message))
  page.on('console', (m) => m.type() === 'error' && errors.push(m.text()))
  const start = Date.now()
  await page.goto(`${BASE}?w=${widget}${query}`)
  await page.getByText('TA-1', { exact: true }).first().waitFor()
  return { page, errors, renderMs: Date.now() - start }
}

const order = (page) => page.evaluate(() => ({ data: window.spike.dataOrder(), screen: window.spike.screenOrder() }))
const same = ({ data, screen }) => JSON.stringify(data.slice(0, screen.length)) === JSON.stringify(screen)

const focused = (page) =>
  page.evaluate(() => {
    const el = document.activeElement
    const row = el?.closest('[role=row], tr')
    return {
      tag: el?.tagName.toLowerCase(),
      role: el?.getAttribute('role'),
      text: (row ?? el)?.textContent?.trim().replace(/\s+/g, ' ').slice(0, 30),
      inWidget: !!el?.closest('[role=grid], [role=table]'),
    }
  })

async function semantics(page) {
  return page.evaluate((sel) => {
    const grid = document.querySelector(sel)
    const rows = [...grid.querySelectorAll('[role=row], tr')]
    const idx = rows.map((r) => r.getAttribute('aria-rowindex')).filter((v) => v !== null).map(Number)
    return {
      role: grid.getAttribute('role') ?? grid.tagName.toLowerCase(),
      name: grid.getAttribute('aria-label') ?? grid.getAttribute('aria-labelledby'),
      rowsInDom: rows.length - 1,
      rowindexMin: idx.length ? Math.min(...idx) : null,
      ariaSelectedOnRows: rows.some((r) => r.hasAttribute('aria-selected')),
      // Across the widget's own root, so a scroller around the table counts too.
      tabStops: (grid.closest('.wx-willow-theme') ?? grid.closest('.p-datatable') ?? grid).querySelectorAll('[tabindex="0"]').length,
      handleFocusable: !!grid.querySelector('[data-pc-section="reorderablerowhandle"][tabindex], .wx-draggable[tabindex]'),
    }
  }, GRID)
}

// Tab in from the last move button, then the arrows, and every key a reorder might use.
async function keyboard(page) {
  const out = {}
  await page.locator('[data-move=bottom]').focus()
  await page.keyboard.press('Tab')
  out.tabIn = await focused(page)
  // A tab stop before the rows (the virtual scroller's container): one more Tab to the rows.
  if (!out.tabIn.inWidget) {
    await page.keyboard.press('Tab')
    out.secondTab = await focused(page)
  }
  await page.keyboard.press('ArrowDown')
  out.arrowDown = await focused(page)
  await page.keyboard.press('ArrowUp')
  out.arrowUp = await focused(page)
  const before = await order(page)
  for (const key of ['Alt+ArrowDown', 'Control+ArrowDown', 'Shift+ArrowDown', 'Space', 'Enter']) await page.keyboard.press(key)
  await page.waitForTimeout(200)
  const after = await order(page)
  out.anyKeyReorders = JSON.stringify(before.data) !== JSON.stringify(after.data)
  out.afterKeys = await focused(page)
  await page.keyboard.press('Tab')
  out.tabOut = await focused(page)
  return out
}

// Selects TA-3 and presses Move down (outside the widget); then the screen against the data.
async function menuMove(page) {
  await page.getByText('Task 3', { exact: true }).click()
  await page.locator('[data-move=down]').click()
  await page.waitForTimeout(300)
  const o = await order(page)
  return {
    first5: o.data.slice(0, 5),
    screenEqualsData: same(o),
    message: await page.locator('[role=status]').textContent(),
    focusAfter: await focused(page),
  }
}

// Drags TA-2 below TA-5 with the mouse, each by its handle (SVAR's icon in the Title cell).
async function drag(page, widget) {
  const from = widget === 'svar'
    ? await page.locator('[role=row][data-id="2"] .wx-draggable').boundingBox()
    : await page.locator('tbody tr').nth(1).locator('[data-pc-section="reorderablerowhandle"]').boundingBox()
  const to = await page.getByText('Task 5', { exact: true }).boundingBox()
  await page.mouse.move(from.x + from.width / 2, from.y + from.height / 2)
  await page.mouse.down()
  for (let i = 1; i <= 12; i++) {
    await page.mouse.move(from.x + from.width / 2, from.y + ((to.y + to.height * 0.8 - from.y) * i) / 12)
  }
  await page.mouse.up()
  await page.waitForTimeout(400)
  const o = await order(page)
  return {
    first6: o.data.slice(0, 6),
    screenFirst6: o.screen.slice(0, 6),
    screenEqualsData: same(o),
    message: await page.locator('[role=status]').textContent(),
    events: await page.evaluate(() => window.spike.events.slice()),
  }
}

// Every color the widget paints, checked against our tokens (UI-SVR-3, UI-TOK-12).
async function themeAudit(page) {
  return page.evaluate((sel) => {
    const probe = document.createElement('div')
    document.body.append(probe)
    const resolve = (value) => {
      probe.style.color = ''
      probe.style.color = value
      return getComputedStyle(probe).color
    }
    const rootStyle = getComputedStyle(document.documentElement)
    const names = []
    const walk = (rules) => {
      for (const r of rules) {
        if (r.style) names.push(...[...r.style].filter((n) => n.startsWith('--color-')))
        if (r.cssRules) walk(r.cssRules)
      }
    }
    for (const sheet of document.styleSheets) walk(sheet.cssRules)
    const allowed = new Set()
    for (const n of new Set(names)) if (rootStyle.getPropertyValue(n)) allowed.add(resolve(`var(${n})`))
    for (const pct of [6, 12, 24, 40, 70]) {
      allowed.add(resolve(`color-mix(in srgb, var(--color-accent) ${pct}%, var(--color-bg))`))
    }
    probe.remove()
    const transparent = (c) => c === 'rgba(0, 0, 0, 0)' || c === 'transparent'
    const grid = document.querySelector(sel)
    const scope = grid.closest('.wx-willow-theme') ?? grid.closest('.p-datatable') ?? grid
    const unmapped = new Map()
    for (const el of [scope, ...scope.querySelectorAll('*')]) {
      const cs = getComputedStyle(el)
      const props = ['color', 'background-color', 'border-top-color', 'border-bottom-color', 'border-left-color', 'border-right-color']
      if (cs.outlineStyle !== 'none') props.push('outline-color')
      for (const p of props) {
        if (p.startsWith('border') && cs[p.replace('color', 'width').replace(/-./g, (m) => m[1].toUpperCase())] === '0px') continue
        const v = cs.getPropertyValue(p)
        if (transparent(v) || allowed.has(v)) continue
        const key = `${p}: ${v}`
        if (!unmapped.has(key)) unmapped.set(key, `${el.tagName.toLowerCase()}.${[...el.classList].join('.')}`.slice(0, 60))
      }
    }
    return { tokensResolved: allowed.size, unmapped: Object.fromEntries(unmapped) }
  }, GRID)
}

async function axe(page) {
  const r = await new AxeBuilder({ page }).include('[role=grid], .p-datatable').withTags(['wcag2a', 'wcag2aa', 'wcag21aa', 'wcag22aa', 'best-practice']).analyze()
  return r.violations.map((v) => `${v.id} (${v.impact}, ${v.nodes.length} nodes)`)
}

for (const [name, widget, extra] of [['svar', 'svar', ''], ['svar_fixed', 'svar', '&fix=1'], ['prime', 'prime', ''], ['prime_fixed', 'prime', '&fix=1&virtual=1']]) {
  const r = {}
  {
    const { page, errors, renderMs } = await open(widget, extra)
    r.renderMs = renderMs
    r.semantics = await semantics(page)
    r.keyboard = await keyboard(page)
    r.licenseNotice = await page.getByText(/license/i).count()
    r.errors = errors
    await page.close()
  }
  for (const theme of ['light', 'dark']) {
    const { page } = await open(widget, `&theme=${theme}${extra}`)
    await page.getByText('Task 2', { exact: true }).click() // a selected row
    r[`theme_${theme}`] = await themeAudit(page)
    r[`axe_${theme}_selected`] = await axe(page)
    await page.close()
  }
  for (const deny of [false, true]) {
    for (const [key, fn] of [['menuMove', menuMove], ['drag', (p) => drag(p, widget)]]) {
      const { page } = await open(widget, (deny ? '&deny=1' : '') + extra)
      r[`${key}${deny ? 'Denied' : 'Allowed'}`] = await fn(page)
      await page.close()
    }
  }
  // 2,000 rows: first render (the median of three), and a menu move to the screen showing it
  // (the mock server's 30 ms included).
  const times = []
  for (let i = 0; i < 3; i++) {
    const { page, renderMs } = await open(widget, `&rows=2000${extra}`)
    times.push(renderMs)
    if (i === 0) {
      r.rowsInDomAtCap = (await order(page)).screen.length
      await page.getByText('Task 3', { exact: true }).click()
      r.moveMsAtCap = await page.evaluate(async () => {
        const start = performance.now()
        document.querySelector('[data-move=down]').click()
        while (window.spike.screenOrder()[3] !== 3) await new Promise((res) => requestAnimationFrame(res))
        return Math.round(performance.now() - start)
      })
    }
    await page.close()
  }
  r.renderMsAtCap = times.sort((a, b) => a - b)[1]
  results[name] = r
}

// PrimeVue with its virtual scroller (?virtual=1), at the cap: render, a menu move, and a drag.
{
  const r = {}
  const times = []
  for (let i = 0; i < 3; i++) {
    const { page, renderMs } = await open('prime', '&rows=2000&virtual=1')
    times.push(renderMs)
    if (i === 0) {
      r.rowsInDomAtCap = (await order(page)).screen.length
      r.dragAllowed = await drag(page, 'prime')
      r.axe = await axe(page)
    }
    await page.close()
  }
  r.renderMsAtCap = times.sort((a, b) => a - b)[1]
  {
    const { page } = await open('prime', '&rows=2000&virtual=1')
    await page.getByText('Task 3', { exact: true }).click()
    r.moveMsAtCap = await page.evaluate(async () => {
      const start = performance.now()
      document.querySelector('[data-move=down]').click()
      while (window.spike.screenOrder()[3] !== 3) await new Promise((res) => requestAnimationFrame(res))
      return Math.round(performance.now() - start)
    })
    await page.close()
  }
  results.prime_virtual = r
}

// Screenshots for the owner: each widget, light and dark, a row selected.
for (const [widget, extra] of [['svar', '&fix=1'], ['prime', '&fix=1&virtual=1']]) {
  for (const theme of ['light', 'dark']) {
    const { page } = await open(widget, `&theme=${theme}${extra}`)
    await page.getByText('Task 2', { exact: true }).click()
    await page.screenshot({ path: `screenshot-${widget}-${theme}.png` })
    await page.close()
  }
}

await browser.close()
writeFileSync(process.env.OUT ?? 'results.json', JSON.stringify(results, null, 2) + '\n')
console.log(JSON.stringify(results, null, 2))
