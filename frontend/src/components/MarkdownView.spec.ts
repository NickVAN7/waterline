import { mount } from '@vue/test-utils'
import { afterEach, describe, expect, it } from 'vitest'

import { expectNoA11yViolations } from '@/test/a11y'

import MarkdownView from './MarkdownView.vue'
import { XSS_CORPUS } from './MarkdownView.xss-corpus'

function render(source: string) {
  return mount(MarkdownView, { props: { source }, attachTo: document.body })
}

afterEach(() => {
  document.body.innerHTML = ''
})

// Elements that run script, load something remote, or submit: none may come out (UI-MD-1).
const DANGEROUS =
  'script, iframe, frame, frameset, object, embed, img, svg, math, style, link, meta, base, form, button, body'

describe('MarkdownView', () => {
  it('renders CommonMark with tables, strikethrough, and autolinks', () => {
    const view = render('A *b* `c`\n\n| H |\n|---|\n| d |\n\n~~gone~~ https://example.com')

    expect(view.find('em').text()).toBe('b')
    expect(view.find('code').text()).toBe('c')
    expect(view.find('table th').text()).toBe('H')
    expect(view.find('table td').text()).toBe('d')
    expect(view.find('s').text()).toBe('gone')
    expect(view.find('a').attributes('href')).toBe('https://example.com')
  })

  it('shows raw HTML as text instead of rendering it', () => {
    const view = render('<b>bold</b>')

    expect(view.find('b').exists()).toBe(false)
    expect(view.text()).toBe('<b>bold</b>')
  })

  it.each([
    ['# One', 'h2'],
    ['## Two', 'h3'],
    ['##### Five', 'h6'],
    ['###### Six', 'h6'],
  ])('shifts %s down a level, to %s, so content never adds an h1', (source, tag) => {
    const view = render(source)

    expect(view.find('h1').exists()).toBe(false)
    expect(view.find(tag).exists()).toBe(true)
  })

  it.each([
    ['# One', 'h4'],
    ['### Three', 'h6'],
  ])(
    "under an h3 (`level` 3), shifts %s to %s, keeping the page's heading order",
    (source, tag) => {
      const view = mount(MarkdownView, { props: { source, level: 3 } })

      expect(view.find(tag).exists()).toBe(true)
      expect(view.findAll('h2, h3')).toHaveLength(0)
    },
  )

  it("drops the inline style a table column's alignment would set", () => {
    const view = render('| H |\n|:-:|\n| d |')

    expect(view.find('td').text()).toBe('d')
    expect(view.find('[style]').exists()).toBe(false)
  })

  it('renders image syntax as a link to the image, never an image', () => {
    const view = render('![The plan](https://example.com/plan.png)')

    expect(view.find('img').exists()).toBe(false)
    const link = view.find('a')
    expect(link.attributes('href')).toBe('https://example.com/plan.png')
    expect(link.text()).toBe('The plan')
  })

  it('names an image link by its address when it has no alt text', () => {
    const view = render('![](https://example.com/plan.png)')

    expect(view.find('a').text()).toBe('https://example.com/plan.png')
  })

  it.each(['https://example.com/', 'http://example.com/', 'mailto:pat@example.com'])(
    'links to %s, with rel="noopener noreferrer"',
    (url) => {
      const link = render(`[go](${url})`).find('a')

      expect(link.attributes('href')).toBe(url)
      expect(link.attributes('rel')).toBe('noopener noreferrer')
    },
  )

  it('gives an autolink rel="noopener noreferrer" too', () => {
    const link = render('see https://example.com').find('a')

    expect(link.attributes('href')).toBe('https://example.com')
    expect(link.attributes('rel')).toBe('noopener noreferrer')
  })

  it("keeps an ordered list's starting number", () => {
    expect(render('3. Third\n4. Fourth').find('ol').attributes('start')).toBe('3')
  })

  it.each([
    'ftp://example.com/f',
    '/projects/PMT',
    '#top',
    'javascript:alert(1)',
    'data:text/html,x',
  ])('renders a link to %s as plain text', (url) => {
    const view = render(`[go](${url})`)

    expect(view.find('a').exists()).toBe(false)
    expect(view.text()).toContain('go')
  })

  it('renders a task list as marks named by their state, not form controls (TD-88)', () => {
    const view = render('- [ ] Draft\n- [x] Review\n- [X] Sign off')

    const boxes = view.findAll('[role="img"]')
    expect(boxes.map((box) => box.attributes('aria-label'))).toEqual(['Not done', 'Done', 'Done'])
    // The check is drawn only on a done item's box.
    expect(boxes.map((box) => box.classes('task-done'))).toEqual([false, true, true])
    expect(view.find('input').exists()).toBe(false)
    expect(view.findAll('li').map((li) => li.text())).toEqual(['Draft', 'Review', 'Sign off'])
  })

  it('leaves "[ ]" outside a list item as text', () => {
    const view = render('[ ] not a task')

    expect(view.find('[role="img"]').exists()).toBe(false)
    expect(view.text()).toBe('[ ] not a task')
  })

  it('updates when its source changes', async () => {
    const view = render('first')

    await view.setProps({ source: 'second' })

    expect(view.text()).toBe('second')
  })

  it('has no accessibility violations', async () => {
    const view = render(
      '# Title\n\nText with [a link](https://example.com).\n\n- [ ] Task\n- [x] Done\n\n| H |\n|---|\n| d |\n\n```\ncode\n```',
    )

    expect(view.findAll('[role="img"]')).toHaveLength(2)
    await expectNoA11yViolations(view)
  })

  describe('XSS corpus (OWASP filter evasion)', () => {
    it.each(XSS_CORPUS)('neutralizes %s', (payload) => {
      const root = render(payload).element as HTMLElement

      expect(root.querySelectorAll(DANGEROUS)).toHaveLength(0)
      const attributes = [...root.querySelectorAll('*')].flatMap((el) => [...el.attributes])
      expect(attributes.filter((a) => /^on/i.test(a.name)).map((a) => a.name)).toEqual([])
      expect(attributes.filter((a) => a.name === 'style').map((a) => a.value)).toEqual([])
      const urls = attributes.filter((a) =>
        ['href', 'src', 'action', 'formaction', 'data'].includes(a.name),
      )
      expect(
        urls.filter((a) => !/^(?:https?:|mailto:)/i.test(a.value)).map((a) => a.value),
      ).toEqual([])
    })
  })
})
