import { mount } from '@vue/test-utils'
import { afterEach, describe, expect, it } from 'vitest'

import { expectNoA11yViolations } from '@/test/a11y'

import MarkdownView, { sections } from './MarkdownView.vue'
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
  it("gives a table's header cells scope=col, in stored content too (DL-366)", () => {
    const view = render('| Who | Can |\n|---|---|\n| Admin | All |')

    expect(view.findAll('th').map((th) => th.attributes('scope'))).toEqual(['col', 'col'])
  })

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

  it('gives headings no id outside docs mode, so stored content never sets one (DL-311)', () => {
    const view = render('# One\n\n## Two')

    expect(view.findAll('[id]')).toHaveLength(0)
  })

  it('outside docs mode, renders no callout, key, image, or link to our own pages (DL-341)', () => {
    const view = render('> [!TIP]\n> Hint\n\n++Esc++ [page](/docs/trash) ![shot](images/a.webp)')

    expect(view.find('.callout').exists()).toBe(false)
    expect(view.find('blockquote').text()).toBe('[!TIP]\nHint')
    expect(view.find('kbd').exists()).toBe(false)
    expect(view.text()).toContain('++Esc++')
    expect(view.find('img').exists()).toBe(false)
    // Neither link is allowed there, so both stay as their source text.
    expect(view.find('a').exists()).toBe(false)
  })

  describe('docs mode (DL-341)', () => {
    function renderDocs(source: string, images: Record<string, string> = {}) {
      return mount(MarkdownView, {
        props: { source, level: 0, docs: true, images },
        attachTo: document.body,
      })
    }

    it('ids each heading by its words, a repeat -2 and on (DL-338)', () => {
      const view = renderDocs('## My work\n\n### The `star`!\n\n## My work')

      expect(view.findAll('h2, h3').map((h) => [h.element.tagName, h.attributes('id')])).toEqual([
        ['H2', 'my-work'],
        ['H3', 'the-star'],
        ['H2', 'my-work-2'],
      ])
    })

    it.each([
      // Each its own tone (DL-364).
      ['TIP', 'callout-success', 'Tip'],
      ['NOTE', 'callout-info', 'Note'],
      ['WARNING', 'callout-danger', 'Warning'],
    ])('renders > [!%s] as a %s box with an icon and the bold label %s', (kind, tone, label) => {
      const view = renderDocs(`> [!${kind}]\n> Keep a copy.`)

      const box = view.get('.callout')
      expect(box.element.tagName).toBe('DIV')
      expect(box.classes()).toContain(tone)
      expect(view.find('blockquote').exists()).toBe(false)
      expect(box.get('strong').text()).toBe(label)
      // The sanitizer keeps the icon's size and paths: without them it draws at 300 by 150.
      const icon = box.get('strong svg')
      expect(icon.attributes()).toMatchObject({
        'aria-hidden': 'true',
        viewBox: '0 0 24 24',
        width: '1.25em',
        height: '1.25em',
        fill: 'none',
        stroke: 'currentColor',
        'stroke-width': '2',
        'stroke-linecap': 'round',
        'stroke-linejoin': 'round',
      })
      expect(icon.findAll('path').every((path) => path.attributes('d'))).toBe(true)
      expect(box.text()).toBe(`${label}Keep a copy.`)
    })

    it('leaves a plain quote a quote', () => {
      const view = renderDocs('> Just a quote')

      expect(view.find('.callout').exists()).toBe(false)
      expect(view.get('blockquote').text()).toBe('Just a quote')
    })

    it('renders ++keys++ as kbd, a plus inside included, their text escaped', () => {
      const view = renderDocs('Press ++Shift+Tab++, then ++<b>++.')

      expect(view.findAll('kbd').map((k) => k.text())).toEqual(['Shift+Tab', '<b>'])
      expect(view.find('b').exists()).toBe(false)
      expect(view.text()).toBe('Press Shift+Tab, then <b>.')
    })

    it('renders a bundled image as itself, with its alt text', () => {
      const view = renderDocs('![The side panel](images/panel.webp)', {
        'images/panel.webp': '/assets/panel-1a2b.webp',
      })

      expect(view.get('img').attributes()).toMatchObject({
        src: '/assets/panel-1a2b.webp',
        alt: 'The side panel',
      })
    })

    it('renders an image with a bundled -dark sibling as both, each marked with its theme (DL-343)', () => {
      const view = renderDocs('![The side panel](images/panel.webp)', {
        'images/panel.webp': '/assets/panel-1a2b.webp',
        'images/panel-dark.webp': '/assets/panel-dark-3c4d.webp',
      })

      // The theme class is on each version's link, so a hidden one leaves no empty link.
      expect(
        view
          .findAll('a')
          .map((a) => [a.classes(), a.attributes('href'), a.get('img').attributes('src')]),
      ).toEqual([
        [['theme-light'], '/assets/panel-1a2b.webp', '/assets/panel-1a2b.webp'],
        [['theme-dark'], '/assets/panel-dark-3c4d.webp', '/assets/panel-dark-3c4d.webp'],
      ])
      expect(view.findAll('img').map((img) => img.attributes('alt'))).toEqual([
        'The side panel',
        'The side panel',
      ])
    })

    it('makes a bundled image a link to it full size, in a new tab, and loads it lazily (DL-363)', () => {
      const view = renderDocs('![The side panel](images/panel.webp)', {
        'images/panel.webp': '/assets/panel-1a2b.webp',
      })

      const link = view.get('a')
      expect(link.attributes()).toMatchObject({
        href: '/assets/panel-1a2b.webp',
        target: '_blank',
      })
      expect(link.attributes('rel')).toContain('noopener')
      // Its name says where it opens (the image's alt, then the hidden words).
      expect(link.text()).toBe('(opens in a new tab)')
      expect(link.get('img').attributes('loading')).toBe('lazy')
    })

    it('renders an image with no -dark sibling once, in both themes', () => {
      const view = renderDocs('![The side panel](images/panel.webp)', {
        'images/panel.webp': '/assets/panel-1a2b.webp',
        'images/other-dark.webp': '/assets/other-dark.webp',
      })

      expect(view.findAll('a').map((a) => a.classes())).toEqual([[]])
      expect(view.findAll('img')).toHaveLength(1)
    })

    it('renders an image that is not bundled, remote included, as a link', () => {
      const view = renderDocs('![Remote](https://example.com/a.png) ![Missing](images/none.webp)')

      expect(view.find('img').exists()).toBe(false)
      expect(view.findAll('a').map((a) => [a.text(), a.attributes('href')])).toEqual([
        ['Remote', 'https://example.com/a.png'],
        ['Missing', 'images/none.webp'],
      ])
    })

    it("links to a path on our own origin, never to another host's //", () => {
      const view = renderDocs('[Trash](/docs/trash#restore) [evil](//evil.example/x)')

      expect(view.findAll('a').map((a) => a.attributes('href'))).toEqual(['/docs/trash#restore'])
      expect(view.text()).toBe('Trash [evil](//evil.example/x)')
    })

    it('has no accessibility violations', async () => {
      const view = renderDocs(
        '## Section\n\n> [!WARNING]\n> Careful.\n\nPress ++Esc++.\n\n![The panel](images/panel.webp)',
        {
          'images/panel.webp': '/assets/panel.webp',
          'images/panel-dark.webp': '/assets/panel-dark.webp',
        },
      )

      // A screenshot's two links included (DL-363).
      expect(view.findAll('.callout, kbd, a[target]')).toHaveLength(4)
      await expectNoA11yViolations(view)
    })
  })

  it('lists the ## sections with the ids their headings get (On this page, DL-340)', () => {
    expect(sections('## Signing in\n\n### Detail\n\n## Signing in')).toEqual([
      { id: 'signing-in', text: 'Signing in' },
      { id: 'signing-in-2', text: 'Signing in' },
    ])
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

    // Docs mode's ids, callouts, keys, and own-origin links keep every payload as harmless.
    it.each(XSS_CORPUS)('neutralizes %s in docs mode', (payload) => {
      const root = mount(MarkdownView, {
        props: { source: payload, level: 0, docs: true },
        attachTo: document.body,
      }).element as HTMLElement

      expect(root.querySelectorAll(DANGEROUS)).toHaveLength(0)
      const attributes = [...root.querySelectorAll('*')].flatMap((el) => [...el.attributes])
      expect(attributes.filter((a) => /^on/i.test(a.name)).map((a) => a.name)).toEqual([])
      expect(attributes.filter((a) => a.name === 'id' && !/^[a-z0-9-]*$/.test(a.value))).toEqual([])
      const urls = attributes.filter((a) =>
        ['href', 'src', 'action', 'formaction', 'data'].includes(a.name),
      )
      expect(
        urls
          .filter((a) => !/^(?:https?:|mailto:|\/(?!\/)|images\/)/i.test(a.value))
          .map((a) => a.value),
      ).toEqual([])
    })
  })
})
