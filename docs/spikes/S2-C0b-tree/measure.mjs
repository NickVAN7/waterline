// Measures both widgets against DL-150's checklist and writes results.json. Run from this folder
// with the dev server up (`npm run dev`): `node measure.mjs`.
import { writeFileSync } from 'node:fs'

import AxeBuilder from '@axe-core/playwright'
import { chromium } from '@playwright/test'

// BASE=http://localhost:5198/ measures the production build (`npx vite build && npx vite preview --port 5198`).
const BASE = process.env.BASE ?? 'http://localhost:5199/'
const browser = await chromium.launch()
const results = {}

async function open(widget, query = '') {
  const context = await browser.newContext({ viewport: { width: 1280, height: 900 } })
  const page = await context.newPage()
  const errors = []
  page.on('pageerror', (e) => errors.push(e.message))
  page.on('console', (m) => m.type() === 'error' && errors.push(m.text()))
  const start = Date.now()
  await page.goto(`${BASE}?w=${widget}${query}`)
  await page.locator('[role=treegrid] [role=row][aria-level]').first().waitFor()
  const renderMs = Date.now() - start
  return { page, errors, renderMs }
}

// Describes the focused element: its role, its row's id or title, and whether it's in the widget.
const focused = (page) =>
  page.evaluate(() => {
    const el = document.activeElement
    const row = el?.closest('[role=row]')
    return {
      tag: el?.tagName.toLowerCase(),
      role: el?.getAttribute('role'),
      text: (row ?? el)?.textContent?.trim().slice(0, 30),
      inWidget: !!el?.closest('[role=treegrid]'),
    }
  })

const rowState = (page, title) =>
  page.evaluate((t) => {
    const row = [...document.querySelectorAll('[role=treegrid] [role=row]')].find((r) =>
      r.textContent.trim().startsWith(t),
    )
    return row ? { expanded: row.getAttribute('aria-expanded'), selected: row.getAttribute('aria-selected') } : 'hidden'
  }, title)

const rowCount = (page) => page.locator('[role=treegrid] [role=row][aria-level]').count()

async function semantics(page) {
  return page.evaluate(() => {
    const grid = document.querySelector('[role=treegrid]')
    const rows = [...grid.querySelectorAll('[role=row]')]
    const body = rows.filter((r) => r.hasAttribute('aria-level'))
    const leaf = body.find((r) => r.textContent.trim().startsWith('Detail'))
    const idx = body.map((r) => r.getAttribute('aria-rowindex')).filter((v) => v !== null).map(Number)
    return {
      gridRole: grid.getAttribute('role'),
      gridName: grid.getAttribute('aria-label') ?? grid.getAttribute('aria-labelledby'),
      rowsInDom: body.length,
      levels: [...new Set(body.map((r) => r.getAttribute('aria-level')))],
      leafExpanded: leaf?.getAttribute('aria-expanded') ?? null,
      rowindexMin: idx.length ? Math.min(...idx) : null,
      headerRowindex: rows[0].getAttribute('aria-rowindex'),
      setsizePosinset: body[0].hasAttribute('aria-setsize') && body[0].hasAttribute('aria-posinset'),
      cellRole: body[0].querySelector('[role]')?.getAttribute('role') ?? null,
      tabStops: grid.querySelectorAll('[tabindex="0"]').length,
    }
  })
}

async function keyboard(page) {
  const out = {}
  await page.locator('[data-move=down]').focus()
  await page.keyboard.press('Tab')
  out.tabIntoWidget = await focused(page)
  await page.keyboard.press('ArrowDown')
  out.arrowDown = await focused(page)
  await page.keyboard.press('ArrowUp')
  out.arrowUp = await focused(page)
  await page.keyboard.press('ArrowLeft')
  out.arrowLeftOnOpenParent = { focus: await focused(page), row: await rowState(page, 'Area 1'), rows: await rowCount(page) }
  await page.keyboard.press('ArrowRight')
  out.arrowRightOnClosedParent = { focus: await focused(page), row: await rowState(page, 'Area 1'), rows: await rowCount(page) }
  await page.keyboard.press('Home') // SVAR toggles a branch only from its tree column
  await page.keyboard.press('Enter')
  out.enter = { focus: await focused(page), row: await rowState(page, 'Area 1'), rows: await rowCount(page) }
  await page.keyboard.press('Enter')
  await page.keyboard.press('Space')
  out.space = { focus: await focused(page), row: await rowState(page, 'Area 1') }
  await page.keyboard.press('Tab')
  out.tabOut = await focused(page)
  return out
}

// Selects "Detail 1.1.1" (id 3), presses Move down, and compares the screen with the data.
async function menuMove(page) {
  await page.getByText('Detail 1.1.1', { exact: true }).click()
  const before = await page.evaluate(() => window.spike.dataOrder().slice(0, 8))
  await page.locator('[data-move=down]').click()
  await page.waitForTimeout(300)
  return page.evaluate((b) => {
    const s = window.spike
    const data = s.dataOrder()
    const screen = s.screenOrder()
    return {
      before: b,
      dataAfter: data.slice(0, 8),
      screenAfter: screen.slice(0, 8),
      screenEqualsData: JSON.stringify(data) === JSON.stringify(screen),
      message: document.querySelector('[role=status]').textContent,
      focusAfter: (document.activeElement?.closest('[role=row]') ?? document.activeElement)?.textContent?.trim().slice(0, 25),
    }
  }, before)
}

// Drags "Detail 1.1.1" below "Detail 1.1.3" with the mouse (SVAR's `reorder`).
async function drag(page) {
  const from = await page.getByText('Detail 1.1.1', { exact: true }).boundingBox()
  const to = await page.getByText('Detail 1.1.3', { exact: true }).boundingBox()
  await page.mouse.move(from.x + 10, from.y + from.height / 2)
  await page.mouse.down()
  for (let i = 1; i <= 10; i++) {
    await page.mouse.move(from.x + 10, from.y + ((to.y + to.height * 0.75 - from.y) * i) / 10)
  }
  await page.mouse.up()
  await page.waitForTimeout(300)
  return page.evaluate(() => {
    const s = window.spike
    const data = s.dataOrder()
    const screen = s.screenOrder()
    return {
      dataAfter: data.slice(0, 8),
      screenAfter: screen.slice(0, 8),
      screenEqualsData: JSON.stringify(data) === JSON.stringify(screen),
      events: s.events.map((e) => `${e.id} ${e.mode} ${e.target}${e.inProgress ? ' (in progress)' : ''}`),
    }
  })
}

// Every color the widget paints, checked against our tokens (UI-SVR-3, UI-TOK-12).
async function themeAudit(page) {
  return page.evaluate(() => {
    const probe = document.createElement('div')
    document.body.append(probe)
    const resolve = (value) => {
      probe.style.color = ''
      probe.style.color = value
      return getComputedStyle(probe).color
    }
    const rootStyle = getComputedStyle(document.documentElement)
    // Every --color-* custom property declared anywhere, looking inside @layer and @media blocks.
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
    // The preset's primary scale mixes the accent toward the page (preset.ts); those count as ours.
    for (const pct of [6, 12, 24, 40, 70]) {
      allowed.add(resolve(`color-mix(in srgb, var(--color-accent) ${pct}%, var(--color-bg))`))
    }
    probe.remove()
    const transparent = (c) => c === 'rgba(0, 0, 0, 0)' || c === 'transparent'
    const grid = document.querySelector('[role=treegrid]')
    const scope = grid.closest('.wx-willow-theme') ?? grid.closest('.p-treetable') ?? grid
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
  })
}

async function axe(page) {
  const r = await new AxeBuilder({ page }).include('[role=treegrid]').withTags(['wcag2a', 'wcag2aa', 'wcag21aa', 'wcag22aa', 'best-practice']).analyze()
  return r.violations.map((v) => `${v.id} (${v.impact}, ${v.nodes.length} nodes)`)
}

for (const [name, widget, fix] of [['svar', 'svar', ''], ['prime', 'prime', ''], ['prime_fixed', 'prime', '&fix=1']]) {
  const r = {}
  {
    const { page, errors, renderMs } = await open(widget, fix)
    r.renderMs = renderMs
    r.semantics = await semantics(page)
    r.axe = await axe(page)
    r.keyboard = await keyboard(page)
    r.licenseNotice = await page.getByText(/license/i).count()
    r.errors = errors
    await page.close()
  }
  for (const theme of ['light', 'dark']) {
    const { page } = await open(widget, `&theme=${theme}${fix}`)
    await page.getByText('Detail 1.1.2', { exact: true }).click() // a selected row and a focused cell
    r[`theme_${theme}`] = await themeAudit(page)
    r[`axe_${theme}_selected`] = await axe(page)
    await page.close()
  }
  for (const deny of [false, true]) {
    const { page } = await open(widget, (deny ? '&deny=1' : '') + fix)
    r[deny ? 'menuMoveDenied' : 'menuMoveAllowed'] = await menuMove(page)
    await page.close()
  }
  if (widget === 'svar') {
    for (const deny of [false, true]) {
      const { page } = await open(widget, deny ? '&deny=1' : '')
      r[deny ? 'dragDenied' : 'dragAllowed'] = await drag(page)
      await page.close()
    }
  }
  results[name] = r
}

// First render at the ranked view's cap (DL-159), every branch open; the median of three loads.
for (const [name, widget] of [['svar', 'svar'], ['prime', 'prime']]) {
  const times = []
  for (let i = 0; i < 3; i++) {
    const { page, renderMs } = await open(widget, '&rows=2000')
    times.push(renderMs)
    results[name].rowsAtCap = await rowCount(page)
    await page.close()
  }
  results[name].renderMsAtCap = times.sort((a, b) => a - b)[1]
  {
    const { page, renderMs } = await open(widget, '&rows=2000&open=none')
    results[name].renderMsAtCapClosed = renderMs
    // A menu move at the cap, every branch open: click to the screen showing it (the mock
    // server's 30 ms included).
    // TreeTable also with ?rebuild=1, every node rebuilt instead of spliced in place.
    for (const [key, extra] of [['moveMsAtCap', ''], ['moveMsAtCapRebuilt', '&rebuild=1']]) {
      if (widget === 'svar' && extra) continue
      await page.goto(`${BASE}?w=${widget}&rows=2000${extra}`)
      await page.locator('[role=treegrid] [role=row][aria-level]').first().waitFor()
      await page.getByText('Detail 1.1.1', { exact: true }).click()
      results[name][key] = await page.evaluate(async () => {
        const start = performance.now()
        document.querySelector('[data-move=down]').click()
        while (window.spike.screenOrder()[2] !== 4) await new Promise((r) => requestAnimationFrame(r))
        return Math.round(performance.now() - start)
      })
    }
    await page.close()
  }
}

await browser.close()
writeFileSync(process.env.OUT ?? 'results.json', JSON.stringify(results, null, 2) + '\n')
console.log(JSON.stringify(results, null, 2))
