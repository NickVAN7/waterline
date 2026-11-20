import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import MarkdownView, { sections } from '@/components/MarkdownView.vue'

import { ORG_PAGES } from '@/app/router'

import { IMAGES, orderPages, PAGES, parsePage, START_HERE } from './guide'

const PAGE =
  '---\ntitle: Trash\ngroup: Using Waterline\norder: 6\ndescription: Bring it back.\n---\n'

describe('parsePage', () => {
  it('reads the front matter and keeps the body after it', () => {
    expect(parsePage('trash', `${PAGE}## Restore\n`)).toEqual({
      slug: 'trash',
      title: 'Trash',
      group: 'Using Waterline',
      order: 6,
      description: 'Bring it back.',
      body: '## Restore\n',
    })
  })

  it('refuses a page without front matter', () => {
    expect(() => parsePage('bare', '## Restore\n')).toThrow('bare: no front matter')
  })

  it('refuses a page missing a field', () => {
    expect(() => parsePage('trash', PAGE.replace('order: 6\n', ''))).toThrow('trash: no order')
  })

  it('refuses a group that is not one of the four (DL-337)', () => {
    expect(() => parsePage('trash', PAGE.replace('Using Waterline', 'Misc'))).toThrow(
      'trash: unknown group Misc',
    )
  })
})

describe('orderPages', () => {
  it("orders by the groups' order, then each page's own", () => {
    const page = (slug: string, group: string, order: number) =>
      parsePage(slug, PAGE.replace('Using Waterline', group).replace('order: 6', `order: ${order}`))

    const ordered = orderPages([
      page('ref', 'Reference', 1),
      page('two', 'Using Waterline', 2),
      page('admin', 'Administration', 1),
      page('one', 'Using Waterline', 1),
      page('start', 'Get started', 9),
    ])

    expect(ordered.map((p) => p.slug)).toEqual(['start', 'one', 'two', 'admin', 'ref'])
  })
})

// The guide as written: these fail on a page that breaks it, before a reader finds it.
describe('the guide', () => {
  it("has DL-337's pages, in its groups and order", () => {
    expect(PAGES.map((p) => [p.group, p.title])).toEqual([
      ['Get started', 'Welcome to Waterline'],
      ['Using Waterline', 'My work'],
      ['Using Waterline', 'Projects'],
      ['Using Waterline', 'Requirements'],
      ['Using Waterline', 'Approvals'],
      ['Using Waterline', 'Members and roles'],
      ['Using Waterline', 'Trash'],
      ['Using Waterline', 'Your account'],
      ['Administration', 'Workspace'],
      ['Administration', 'Organizations'],
      ['Administration', 'System status'],
      ['Reference', 'Keyboard and accessibility'],
    ])
  })

  it('has a page for each Start here card (DL-339)', () => {
    const slugs = PAGES.map((p) => p.slug)
    expect(START_HERE.filter((card) => !slugs.includes(card.slug))).toEqual([])
  })

  it("takes no org page's name as a slug, so a `docs` org keeps its pages (DL-309)", () => {
    expect(PAGES.filter((p) => (ORG_PAGES as readonly string[]).includes(p.slug))).toEqual([])
  })

  it.each(PAGES.map((p) => [p.slug, p]))(
    '%s has no # heading: the page gives the h1 (UI-SHL-8)',
    (_slug, page) => {
      expect(page.body).not.toMatch(/^# /m)
    },
  )

  it.each(PAGES.map((p) => [p.slug, p]))(
    "%s keeps every section's id once rendered",
    (_slug, page) => {
      const view = mount(MarkdownView, {
        props: { source: page.body, level: 0, docs: true, images: IMAGES },
      })

      const ids = view.findAll('h2').map((h) => h.attributes('id'))
      expect(ids).toEqual(sections(page.body).map((s) => s.id))
    },
  )

  it.each(PAGES.map((p) => [p.slug, p]))(
    "%s links only to the guide's own pages and sections",
    (_slug, page) => {
      // Every link but an image's: a relative or bare `#` link would render as its raw text.
      const links = [...page.body.matchAll(/(?<!!)\[[^\]]*\]\(([^)]*)\)/g)]
        .map((m) => m[1]!)
        .filter((link) => !/^(?:https?:|mailto:)/.test(link))
      const broken = links.filter((link) => {
        const [, slug, hash] = /^\/docs\/([a-z-]+)(?:#(.+))?$/.exec(link) ?? []
        const target = PAGES.find((p) => p.slug === slug)
        return !target || (hash !== undefined && !sections(target.body).some((s) => s.id === hash))
      })
      expect(broken).toEqual([])
    },
  )

  it.each(PAGES.map((p) => [p.slug, p]))(
    '%s shows only bundled images, each with alt text (DL-343)',
    (_slug, page) => {
      const images = [...page.body.matchAll(/!\[([^\]]*)\]\(([^)]*)\)/g)]
      expect(images.filter(([, alt, src]) => !alt!.trim() || !IMAGES[src!])).toEqual([])
    },
  )

  it('shows each image in both themes: the light file, with its -dark sibling (DL-343)', () => {
    const shown = PAGES.flatMap((p) => [...p.body.matchAll(/!\[[^\]]*\]\((images\/[^)]*)\)/g)]).map(
      (m) => m[1]!,
    )
    expect(shown.filter((src) => src.includes('-dark.'))).toEqual([])
    expect(shown.filter((src) => !IMAGES[src.replace(/(\.[a-z]+)$/, '-dark$1')])).toEqual([])
  })

  it('bundles no image that no page shows', () => {
    const shown = PAGES.map((p) => p.body).join('\n')
    const unused = Object.keys(IMAGES).filter(
      (src) => !shown.includes(`(${src.replace('-dark.', '.')})`),
    )
    expect(unused).toEqual([])
  })
})
