import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError, NETWORK_ERROR } from '@/api/client'

import {
  retryFromSubmit,
  ANNOUNCE_DELAY_MS,
  FORM_MESSAGES,
  refetchNeeded,
  useFormErrors,
} from './useFormErrors'

const LABELS = { email: 'Email', password: 'Password' }

function apiError(status: number, code: string, details: Record<string, unknown> = {}) {
  return new ApiError(status, { code, message: `server says ${code}`, details })
}

function invalid(...fields: [string, string][]) {
  return apiError(422, 'validation_error', {
    fields: fields.map(([name, message]) => ({ loc: ['body', name], message, type: 'x' })),
  })
}

beforeEach(() => {
  vi.useFakeTimers()
})

afterEach(() => {
  vi.useRealTimers()
})

describe('useFormErrors', () => {
  it("shows a 422's errors under their fields, focuses the first, and names them", () => {
    const errors = useFormErrors(LABELS)

    const focus = errors.apply(invalid(['password', 'Too short.'], ['email', 'Not an email.']))
    vi.advanceTimersByTime(ANNOUNCE_DELAY_MS)

    expect(errors.fieldErrors.value).toEqual({ email: 'Not an email.', password: 'Too short.' })
    expect(focus).toBe('email')
    expect(errors.announcement.value).toBe('2 fields need attention: Email, Password')
    expect(errors.alert.value).toBeNull()
  })

  it('clears the announcement and sets it again, so a repeat failure is read again', () => {
    const errors = useFormErrors(LABELS)
    errors.apply(invalid(['password', 'Too short.']))
    vi.advanceTimersByTime(ANNOUNCE_DELAY_MS)

    errors.apply(invalid(['password', 'Too short.']))

    vi.advanceTimersByTime(ANNOUNCE_DELAY_MS - 1)
    expect(errors.announcement.value).toBe('')
    vi.advanceTimersByTime(1)
    expect(errors.announcement.value).toBe('1 field needs attention: Password')
  })

  it('drops the alert and announces the dismissal, again on a repeat', () => {
    const errors = useFormErrors(LABELS)
    errors.apply(invalid(['password', 'Too short.'], ['other', 'Something else.']))
    vi.advanceTimersByTime(ANNOUNCE_DELAY_MS)

    errors.dismissAlert()
    expect([errors.alert.value, errors.announcement.value]).toEqual([null, ''])
    vi.advanceTimersByTime(ANNOUNCE_DELAY_MS)
    expect(errors.announcement.value).toBe('Alert dismissed')

    // A second dismiss empties the region first, so the same text is read again.
    errors.dismissAlert()
    expect(errors.announcement.value).toBe('')
    vi.advanceTimersByTime(ANNOUNCE_DELAY_MS)
    expect(errors.announcement.value).toBe('Alert dismissed')
  })

  it('says "1 field" for one', () => {
    const errors = useFormErrors(LABELS)

    errors.apply(invalid(['password', 'Too short.']))
    vi.advanceTimersByTime(ANNOUNCE_DELAY_MS)

    expect(errors.announcement.value).toBe('1 field needs attention: Password')
  })

  it('shows every message for a field that has several, none dropped', () => {
    const errors = useFormErrors(LABELS)

    errors.apply(invalid(['password', 'Too short.'], ['password', 'Same as your email.']))

    expect(errors.fieldErrors.value).toEqual({ password: 'Too short. Same as your email.' })
    expect(errors.alert.value).toBeNull()
  })

  it('puts an error for a field the form does not show in the form alert', () => {
    const errors = useFormErrors(LABELS)

    const focus = errors.apply(invalid(['body', 'Send exactly one.']))

    expect(errors.fieldErrors.value).toEqual({})
    expect(errors.alert.value).toEqual({ tone: 'danger', message: 'Send exactly one.' })
    expect(focus).toBe('alert')
  })

  it.each([
    [apiError(403, 'forbidden'), { tone: 'danger', message: FORM_MESSAGES.forbidden }],
    [
      apiError(409, 'conflict'),
      { tone: 'warning', message: FORM_MESSAGES.conflict, action: 'reload' },
    ],
    [
      apiError(0, NETWORK_ERROR),
      { tone: 'danger', message: FORM_MESSAGES.network, action: 'retry' },
    ],
    [apiError(500, 'internal_error'), { tone: 'danger', message: FORM_MESSAGES.generic }],
  ])('shows %s as a form alert in our own words', (error, alert) => {
    const errors = useFormErrors(LABELS)

    expect(errors.apply(error)).toBe('alert')
    expect(errors.alert.value).toEqual(alert)
  })

  it("shows the server's message for the codes the form names", () => {
    const errors = useFormErrors(LABELS, { serverMessageCodes: ['invalid_credentials'] })

    errors.apply(apiError(401, 'invalid_credentials'))

    expect(errors.alert.value).toEqual({
      tone: 'danger',
      message: 'server says invalid_credentials',
    })
  })

  it('lets anything that is not an API error through', () => {
    const bug = new RangeError('bug')

    expect(() => useFormErrors(LABELS).apply(bug)).toThrow(bug)
  })

  it('clears what a previous failure showed', () => {
    const errors = useFormErrors(LABELS)
    errors.apply(invalid(['email', 'Not an email.']))

    errors.apply(apiError(500, 'internal_error'))

    expect(errors.fieldErrors.value).toEqual({})
    expect(errors.announcement.value).toBe('')
  })

  it('keeps every error on each field, with its type, for a field that shows them elsewhere', () => {
    const errors = useFormErrors(LABELS)

    errors.apply(
      apiError(422, 'validation_error', {
        fields: [
          { loc: ['body', 'password'], message: 'Too short.', type: 'too_short' },
          { loc: ['body', 'password'], message: 'Same as your email.', type: 'same_as_email' },
          { loc: ['body', 'other'], message: 'Not shown.', type: 'x' },
        ],
      }),
    )

    expect(errors.fieldProblems.value).toEqual({
      password: [
        { message: 'Too short.', type: 'too_short' },
        { message: 'Same as your email.', type: 'same_as_email' },
      ],
    })
  })

  it("clears a field's kept errors when the user edits it, and all of them on the next submit", () => {
    const errors = useFormErrors(LABELS)
    errors.apply(invalid(['email', 'Not an email.'], ['password', 'Too short.']))

    errors.clearField('email')
    expect(Object.keys(errors.fieldProblems.value)).toEqual(['password'])

    errors.reset()
    expect(errors.fieldProblems.value).toEqual({})
  })

  it('clears one field when the user edits it', () => {
    const errors = useFormErrors(LABELS)
    errors.apply(invalid(['email', 'Not an email.'], ['password', 'Too short.']))

    errors.clearField('email')

    expect(errors.fieldErrors.value).toEqual({ password: 'Too short.' })
  })

  describe('requireFilled', () => {
    it('marks each empty field required and returns the first', () => {
      const errors = useFormErrors(LABELS)

      const first = errors.requireFilled({ email: '', password: '' })
      vi.advanceTimersByTime(ANNOUNCE_DELAY_MS)

      expect(first).toBe('email')
      expect(errors.fieldErrors.value).toEqual({
        email: 'This is required.',
        password: 'This is required.',
      })
      expect(errors.announcement.value).toBe('2 fields need attention: Email, Password')
    })

    it('lets a filled form through, clearing earlier errors', () => {
      const errors = useFormErrors(LABELS)
      errors.requireFilled({ email: '', password: 'x' })

      expect(errors.requireFilled({ email: 'a@b.example', password: ' ' })).toBeNull()
      expect(errors.fieldErrors.value).toEqual({})
    })
  })
})

describe('retryFromSubmit (UI-FRM-7)', () => {
  it("focuses the form's submit button, then repeats the action", () => {
    const form = document.body.appendChild(document.createElement('form'))
    form.innerHTML = '<button type="button">Cancel</button><button type="submit">Save</button>'
    let focusedAtRetry: Element | null = null

    retryFromSubmit({ value: form }, () => (focusedAtRetry = document.activeElement))()

    expect(focusedAtRetry).toBe(form.querySelector('button[type=submit]'))
    form.remove()
  })
})

describe('refetchNeeded (UI-FRM-7, DL-116)', () => {
  const invalid = (loc: string, type: string) =>
    new ApiError(422, {
      code: 'validation_error',
      message: '',
      details: { fields: [{ loc: ['body', loc], message: '', type }] },
    })

  it.each([
    ['a 403', new ApiError(403, { code: 'forbidden', message: '', details: {} }), true],
    ['confirmation_required', invalid('export_control_confirmed', 'confirmation_required'), true],
    [
      'confirmation_not_needed',
      invalid('export_control_confirmed', 'confirmation_not_needed'),
      true,
    ],
    ['another type on the field', invalid('export_control_confirmed', 'other'), false],
    ['the type on another field', invalid('confirmed_member_ids', 'confirmation_required'), false],
    ['members_changed', invalid('confirmed_member_ids', 'members_changed'), false],
    ['a 409', new ApiError(409, { code: 'conflict', message: '', details: {} }), false],
    ['not an ApiError', new Error('boom'), false],
  ])('%s → %s', (_name, error, expected) => {
    expect(refetchNeeded(error)).toBe(expected)
  })
})
