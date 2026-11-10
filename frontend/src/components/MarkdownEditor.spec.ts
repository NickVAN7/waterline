import { mount } from '@vue/test-utils'
import PrimeVue from 'primevue/config'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'

import { expectNoA11yViolations } from '@/test/a11y'
import { stubResizeObserver } from '@/test/overlay'

import MarkdownEditor from './MarkdownEditor.vue'

function mountEditor(props: { modelValue: string; error?: string; required?: boolean }) {
  return mount(MarkdownEditor, {
    props: {
      id: 'description',
      label: 'Description',
      ...props,
      'onUpdate:modelValue': (value: string) => editor.setProps({ modelValue: value }),
    },
    global: { plugins: [PrimeVue] },
    attachTo: document.body,
  })
}
let editor: ReturnType<typeof mountEditor>

beforeEach(stubResizeObserver)

afterEach(() => {
  editor.unmount()
  document.body.innerHTML = ''
})

const tab = (name: string) => editor.findAll('[role="tab"]').find((t) => t.text() === name)!
const panel = (name: string) =>
  editor.find(`[role="tabpanel"][aria-labelledby="${tab(name).attributes('id')}"]`)

describe('MarkdownEditor', () => {
  it('opens on Write, with the textarea named by its label', () => {
    editor = mountEditor({ modelValue: 'Some *text*' })

    expect(editor.find('[role="tablist"]').attributes('aria-label')).toBe('Description')
    expect(tab('Write').attributes('aria-selected')).toBe('true')
    expect(tab('Preview').attributes('aria-selected')).toBe('false')
    expect(panel('Write').attributes('tabindex')).toBe('-1')
    // The hidden preview isn't rendered on every keystroke.
    expect(editor.find('em').exists()).toBe(false)
    const textarea = editor.find('textarea')
    expect(editor.find('label[for="description"]').text()).toBe('Description')
    expect(textarea.attributes('id')).toBe('description')
    expect((textarea.element as HTMLTextAreaElement).value).toBe('Some *text*')
  })

  it('binds what is typed to its model', async () => {
    editor = mountEditor({ modelValue: '' })

    await editor.find('textarea').setValue('New text')

    expect(editor.emitted('update:modelValue')).toEqual([['New text']])
  })

  it('previews what was typed through the sanitizing renderer', async () => {
    editor = mountEditor({ modelValue: '' })
    await editor.find('textarea').setValue('# Plan\n\n<script>alert(1)</script>')

    await tab('Preview').trigger('click')

    expect(tab('Preview').attributes('aria-selected')).toBe('true')
    expect(panel('Preview').find('h2').text()).toBe('Plan')
    expect(panel('Preview').find('script').exists()).toBe(false)
    expect(panel('Preview').text()).toContain('<script>alert(1)</script>')
  })

  it('keeps the same textarea across a preview, so its undo history and size survive', async () => {
    editor = mountEditor({ modelValue: 'text' })
    const before = editor.find('textarea').element

    await tab('Preview').trigger('click')
    await tab('Write').trigger('click')

    expect(editor.find('textarea').element).toBe(before)
  })

  it('says there is nothing to preview when the text is blank', async () => {
    editor = mountEditor({ modelValue: '  \n' })

    await tab('Preview').trigger('click')

    expect(panel('Preview').text()).toBe('Nothing to preview.')
  })

  it('returns to Write and focuses the textarea when focused from Preview', async () => {
    editor = mountEditor({ modelValue: 'text' })
    await tab('Preview').trigger('click')

    await (editor.vm as unknown as { focus: () => Promise<void> }).focus()

    expect(tab('Write').attributes('aria-selected')).toBe('true')
    expect(document.activeElement).toBe(editor.find('textarea').element)
  })

  it('marks the textarea invalid and describes it by the error', () => {
    editor = mountEditor({ modelValue: '', error: 'Too long.', required: true })

    const textarea = editor.find('textarea')
    expect(textarea.attributes('aria-invalid')).toBe('true')
    expect(textarea.attributes('aria-required')).toBe('true')
    const describedBy = textarea.attributes('aria-describedby')!
    expect(editor.find(`#${describedBy}`).text()).toBe('Too long.')
  })

  it('has no accessibility violations on either tab', async () => {
    editor = mountEditor({ modelValue: '- [ ] A task\n\n[link](https://example.com)' })
    await expectNoA11yViolations(editor)

    await tab('Preview').trigger('click')

    expect(panel('Preview').findAll('[role="img"]')).toHaveLength(1)
    await expectNoA11yViolations(editor)
  })
})
