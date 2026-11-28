import { afterEach, describe, expect, it, vi } from 'vitest'

import type Alert from '@/components/Alert.vue'

import { messageFor, useActionFailure } from './useActionFailure'

type AlertRef = InstanceType<typeof Alert>

const MESSAGES = { 403: 'Not allowed.', 404: 'Gone.', 409: 'Changed.', other: 'Try again.' }

afterEach(() => {
  document.body.innerHTML = ''
})

describe('messageFor', () => {
  it.each([
    [403, 'Not allowed.'],
    [404, 'Gone.'],
    [409, 'Changed.'],
    [500, 'Try again.'],
    [0, 'Try again.'],
  ])('gives status %i its message', (status, expected) => {
    expect(messageFor(status, MESSAGES)).toBe(expected)
  })

  // Bug: a status with no message of its own shown as nothing.
  it('falls back to `other` for a status the action has no message for', () => {
    expect(messageFor(404, { 403: 'Not allowed.', other: 'Try again.' })).toBe('Try again.')
  })
})

describe('useActionFailure', () => {
  // The control that held focus went with its row or the permission (UI-FRM-7). The alert ref is
  // set by hand here; that `show` waits for the alert to render before focusing it is guarded by
  // the views' specs (TrashView's and RequirementView's 403 cases).
  it('shows the message, counts it, and moves focus to the alert when focus was lost', async () => {
    const failure = useActionFailure()
    const focus = vi.fn()
    failure.alert.value = { focus } as unknown as AlertRef

    await failure.show('Gone.')

    expect([failure.message.value, failure.count.value]).toEqual(['Gone.', 1])
    expect(focus).toHaveBeenCalledOnce()
  })

  // Bug: focus pulled away from a control the user still has.
  it('leaves focus where it is when the control is still there', async () => {
    const failure = useActionFailure()
    const focus = vi.fn()
    failure.alert.value = { focus } as unknown as AlertRef
    const button = document.createElement('button')
    document.body.append(button)
    button.focus()

    await failure.show('Try again.')

    expect(focus).not.toHaveBeenCalled()
    expect(document.activeElement).toBe(button)
  })

  // The alert is keyed on the count, so the same words are announced again (UI-FBK-13).
  it('counts each failure, the same words again included', async () => {
    const failure = useActionFailure()

    await failure.show('Try again.')
    await failure.show('Try again.')

    expect(failure.count.value).toBe(2)
  })
})
