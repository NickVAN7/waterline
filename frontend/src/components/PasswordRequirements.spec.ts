import { mount } from '@vue/test-utils'
import { afterEach, describe, expect, it } from 'vitest'

import { expectNoA11yViolations } from '@/test/a11y'
import { PASSWORD_POLICY } from '@/test/api'

import PasswordRequirements from './PasswordRequirements.vue'

function mountList(props: Partial<InstanceType<typeof PasswordRequirements>['$props']> = {}) {
  return mount(PasswordRequirements, {
    props: {
      id: 'new_password-requirements',
      requirements: PASSWORD_POLICY.requirements,
      password: '',
      email: 'casey@harbor.example',
      username: 'casey',
      current: 'harbor-demo',
      failed: [],
      ...props,
    },
    attachTo: document.body,
  })
}

/** Each line's text as a screen reader reads it (hidden text included). */
function lines(wrapper: ReturnType<typeof mountList>) {
  return wrapper.findAll('li').map((li) => li.text().replace(/\s+/g, ' ').trim())
}

afterEach(() => {
  document.body.innerHTML = ''
})

describe('PasswordRequirements', () => {
  it('lists every requirement as not met before anything is typed', async () => {
    const wrapper = mountList()

    expect(lines(wrapper)).toEqual([
      'Not met: At least 8 characters',
      'Not met: Not your email',
      'Not met: Not your username',
      'Not met: Not your current password',
    ])
    await expectNoA11yViolations(wrapper)
  })

  it.each([
    ['seven77', 'Not met: At least 8 characters'],
    ['eight888', 'Met: At least 8 characters'],
    // Characters, as the server counts them: four emoji are 8 UTF-16 units but 4 characters.
    ['😀😀😀😀', 'Not met: At least 8 characters'],
  ])('checks the length of %s in characters', (password, expected) => {
    expect(lines(mountList({ password }))[0]).toBe(expected)
  })

  it.each([
    ['CASEY@harbor.example', 1, 'Not met: Not your email'],
    ['Casey', 2, 'Not met: Not your username'],
    ['harbor-demo', 3, 'Not met: Not your current password'],
    ['a long passphrase', 1, 'Met: Not your email'],
    ['a long passphrase', 2, 'Met: Not your username'],
    ['a long passphrase', 3, 'Met: Not your current password'],
  ])('checks %s against line %i', (password, line, expected) => {
    expect(lines(mountList({ password }))[line]).toBe(expected)
  })

  it('folds case the way the server does, so ß matches ss', () => {
    expect(lines(mountList({ username: 'strasse', password: 'STRAßE' }))[2]).toBe(
      'Not met: Not your username',
    )
  })

  it('shows a requirement it can check without its data as plain text', () => {
    const wrapper = mountList({ password: 'a long passphrase', current: undefined })

    expect(lines(wrapper)[3]).toBe('Not your current password')
    expect(wrapper.findAll('li')[3]!.find('svg').exists()).toBe(false)
  })

  it('shows a requirement it does not know as plain text', () => {
    const wrapper = mountList({
      requirements: [{ code: 'too_long', label: 'At most 256 characters', value: 256 }],
      password: 'x',
    })

    expect(lines(wrapper)).toEqual(['At most 256 characters'])
  })

  it('marks a line the server refused with a visible "Not met:", read once', () => {
    const wrapper = mountList({ password: 'eight888', failed: ['too_short'] })

    const line = wrapper.findAll('li')[0]!
    expect(line.text().replace(/\s+/g, ' ').trim()).toBe('Not met: At least 8 characters')
    expect(line.find('.sr-only').exists()).toBe(false)
    expect(line.classes()).toContain('text-tone-danger-fg')
  })

  it('is not a live region, so typing announces nothing', () => {
    const wrapper = mountList()

    expect(wrapper.find('[aria-live]').exists()).toBe(false)
    expect(wrapper.find('[role=status], [role=alert]').exists()).toBe(false)
  })

  it('is left out when there are no requirements', () => {
    expect(mountList({ requirements: [] }).find('ul').exists()).toBe(false)
  })
})
