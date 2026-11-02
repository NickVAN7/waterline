import { flushPromises, mount } from '@vue/test-utils'
import PrimeVue from 'primevue/config'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { client } from '@/api/client'
import type { components } from '@/api/schema'
import { expectNoA11yViolations } from '@/test/a11y'
import { failed, ok } from '@/test/api'
import { stubDialog, stubResizeObserver } from '@/test/overlay'
import { requirementId, requirementItem, requirementRead } from '@/test/requirements'

import CreateRequirementDialog from './CreateRequirementDialog.vue'

type ProjectType = components['schemas']['ProjectType']

const id = requirementId
const item = requirementItem

async function openDialog(type: ProjectType = 'software', items = [item(1, 'Invoicing')]) {
  const wrapper = mount(CreateRequirementDialog, {
    props: { projectKey: 'ERP', projectType: type, items },
    global: { plugins: [PrimeVue] },
    attachTo: document.body,
  })
  await (wrapper.vm as unknown as { open: () => Promise<void> }).open()
  await flushPromises()
  return wrapper
}

const field = (selector: string) => document.querySelector<HTMLInputElement>(selector)!
const title = () => field('#create-requirement-title')
const description = () =>
  document.querySelector<HTMLTextAreaElement>('#create-requirement-description')!
const parent = () => document.querySelector<HTMLSelectElement>('#create-requirement-parent')!
const priority = () => document.querySelector<HTMLSelectElement>('#create-requirement-priority')!
async function fillTitle(value: string) {
  title().value = value
  title().dispatchEvent(new Event('input'))
  await flushPromises()
}
async function submit() {
  document.querySelector('form')!.requestSubmit()
  await flushPromises()
}

beforeEach(() => {
  stubResizeObserver()
  stubDialog()
})
afterEach(() => {
  document.body.innerHTML = ''
  vi.restoreAllMocks()
})

describe('CreateRequirementDialog', () => {
  it.each<[ProjectType, string]>([
    ['software', '## Context\n\n\n## Acceptance Criteria\n\n1. '],
    ['general', '## Context\n\n\n## Acceptance Criteria\n\n1. '],
    [
      'erp',
      '## Business Process\n\n\n## Current State\n\n\n## Future State\n\n\n## Acceptance Criteria\n\n1. ',
    ],
  ])(
    'opens a %s project with its template, Medium, and the top level (DL-149)',
    async (type, template) => {
      await openDialog(type)

      expect(document.querySelector('dialog[open] h2')!.textContent).toBe('Create a requirement')
      expect(document.activeElement).toBe(title())
      expect(description().value).toBe(template)
      expect(priority().value).toBe('medium')
      expect([...priority().options].map((o) => o.text)).toEqual([
        'Critical',
        'High',
        'Medium',
        'Low',
      ])
      expect([...parent().options].map((o) => o.text)).toEqual([
        'Top level (no parent)',
        'ERP-RQ-1 Invoicing',
      ])
      // No restriction fields: a new requirement starts at the project's level (DL-251).
      expect(document.querySelector('dialog[open]')!.textContent).not.toMatch(/Restriction/)
      await expectNoA11yViolations(document.querySelector<HTMLElement>('dialog[open]')!)
    },
  )

  it('creates it, sending what was entered, then closes and says which row is new', async () => {
    const post = vi.spyOn(client, 'POST').mockResolvedValue(ok(requirementRead(7, 'Refunds')))
    const wrapper = await openDialog()
    await fillTitle('Refunds')
    priority().value = 'high'
    priority().dispatchEvent(new Event('change'))
    parent().value = id(1)
    parent().dispatchEvent(new Event('change'))

    await submit()

    expect(post).toHaveBeenCalledWith('/api/projects/{key}/requirements', {
      params: { path: { key: 'ERP' } },
      body: {
        title: 'Refunds',
        description_md: '## Context\n\n\n## Acceptance Criteria\n\n1. ',
        priority: 'high',
        parent_id: id(1),
        restriction_categories: [],
      },
    })
    expect(wrapper.emitted('created')).toEqual([[requirementRead(7, 'Refunds')]])
    expect(document.querySelector('dialog[open]')).toBeNull()
  })

  it('sends no parent for the top level', async () => {
    const post = vi.spyOn(client, 'POST').mockResolvedValue(ok(requirementRead(7, 'Refunds')))
    await openDialog()
    await fillTitle('Refunds')

    await submit()

    expect((post.mock.calls[0]![1] as { body: { parent_id: unknown } }).body.parent_id).toBeNull()
  })

  it('asks for a title before sending anything, with focus on it', async () => {
    const post = vi.spyOn(client, 'POST')
    await openDialog()
    await fillTitle('   ')

    await submit()

    expect(post).not.toHaveBeenCalled()
    expect(title().getAttribute('aria-invalid')).toBe('true')
    expect(document.activeElement).toBe(title())
  })

  it("shows the server's 422 on its field, with focus there (UI-FRM-6)", async () => {
    vi.spyOn(client, 'POST').mockResolvedValue(
      failed(422, {
        code: 'validation_error',
        message: 'The request is invalid.',
        details: {
          fields: [
            {
              loc: ['body', 'title'],
              message: 'At most 200 characters.',
              type: 'string_too_long',
            },
          ],
        },
      }),
    )
    const wrapper = await openDialog()
    await fillTitle('x'.repeat(201))

    await submit()

    const describedBy = title().getAttribute('aria-describedby')!
    expect(document.getElementById(describedBy.split(' ').at(-1)!)!.textContent).toContain(
      'At most 200 characters.',
    )
    expect(document.activeElement).toBe(title())
    expect(wrapper.emitted('created')).toBeUndefined()
  })

  it('a 422 on the description returns to Write and focuses the editor', async () => {
    vi.spyOn(client, 'POST').mockResolvedValue(
      failed(422, {
        code: 'validation_error',
        message: 'The request is invalid.',
        details: {
          fields: [
            {
              loc: ['body', 'description_md'],
              message: 'At most 20,000 characters.',
              type: 'string_too_long',
            },
          ],
        },
      }),
    )
    await openDialog()
    await fillTitle('Refunds')

    await submit()

    expect(document.activeElement).toBe(description())
    expect(description().getAttribute('aria-invalid')).toBe('true')
  })

  it('a 403 says so in the form and tells the page, which reloads what the user may do', async () => {
    vi.spyOn(client, 'POST').mockResolvedValue(
      failed(403, { code: 'forbidden', message: '', details: {} }),
    )
    const wrapper = await openDialog()
    await fillTitle('Refunds')

    await submit()

    const alert = document.querySelector<HTMLElement>('dialog[open] [role=alert]')!
    expect(alert.textContent).toContain("You don't have permission")
    expect(alert.contains(document.activeElement)).toBe(true)
    expect(wrapper.emitted('refused')).toHaveLength(1)
    expect(wrapper.emitted('created')).toBeUndefined()
  })

  it('a 404 with a parent chosen: the page reloads the tree, and the field goes back to the top level, saying why', async () => {
    vi.spyOn(client, 'POST').mockResolvedValue(
      failed(404, { code: 'not_found', message: '', details: {} }),
    )
    const wrapper = await openDialog()
    await fillTitle('Refunds')
    parent().value = id(1)
    parent().dispatchEvent(new Event('change'))

    await submit()

    expect(wrapper.emitted('stale')).toHaveLength(1)
    expect(parent().value).toBe('')
    expect(parent().getAttribute('aria-invalid')).toBe('true')
    expect(document.activeElement).toBe(parent())
    expect(document.querySelector('dialog[open]')!.textContent).toContain(
      "The parent you chose isn't there any more.",
    )
  })

  it('a network failure offers Retry, which sends it again', async () => {
    const post = vi
      .spyOn(client, 'POST')
      .mockResolvedValueOnce(failed(503, { code: 'network_error', message: '', details: {} }))
      .mockResolvedValue(ok(requirementRead(7, 'Refunds')))
    const wrapper = await openDialog()
    await fillTitle('Refunds')
    await submit()

    ;[...document.querySelectorAll<HTMLButtonElement>('dialog[open] button')]
      .find((b) => b.textContent!.trim() === 'Retry')!
      .click()
    await flushPromises()

    expect(post).toHaveBeenCalledTimes(2)
    expect(wrapper.emitted('created')).toHaveLength(1)
  })

  it("a 404 at the top level doesn't blame a parent: the page reloads, which shows the project gone", async () => {
    vi.spyOn(client, 'POST').mockResolvedValue(
      failed(404, { code: 'not_found', message: '', details: {} }),
    )
    const wrapper = await openDialog()
    await fillTitle('Refunds')

    await submit()

    expect(wrapper.emitted('stale')).toHaveLength(1)
    expect(parent().getAttribute('aria-invalid')).toBeNull()
  })

  it('sends once, however often Create is pressed while it is sending', async () => {
    let answer: (value: unknown) => void = () => {}
    const post = vi
      .spyOn(client, 'POST')
      .mockReturnValue(new Promise((resolve) => (answer = resolve)) as never)
    await openDialog()
    await fillTitle('Refunds')

    document.querySelector('form')!.requestSubmit()
    document.querySelector('form')!.requestSubmit()
    answer(ok(requirementRead(7, 'Refunds')))
    await flushPromises()

    expect(post).toHaveBeenCalledTimes(1)
  })

  it('opens on Write each time, with the template again', async () => {
    const wrapper = await openDialog()
    ;[...document.querySelectorAll<HTMLElement>('[role=tab]')]
      .find((tab) => tab.textContent === 'Preview')!
      .click()
    await flushPromises()

    await (wrapper.vm as unknown as { open: () => Promise<void> }).open()
    await flushPromises()

    const write = [...document.querySelectorAll<HTMLElement>('[role=tab]')].find(
      (tab) => tab.textContent === 'Write',
    )!
    expect(write.getAttribute('aria-selected')).toBe('true')
    expect(description().value).toContain('## Acceptance Criteria')
  })
})
