import { mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { defineComponent, nextTick, ref } from 'vue'

import { ApiError } from '@/api/client'

import { AVAILABILITY_DELAY_MS, useAvailability } from './useAvailability'

type Answer = { available: boolean; problem: string | null }

function setup(check: (value: string) => Promise<Answer>, skip?: (value: string) => boolean) {
  const value = ref('')
  let message!: ReturnType<typeof useAvailability>['message']
  mount(
    defineComponent({
      setup() {
        message = useAvailability(value, 'Slug', check, skip).message
        return () => null
      },
    }),
  )
  return { value, message: () => message.value }
}

async function type(value: { value: string }, text: string) {
  value.value = text
  await nextTick()
}

beforeEach(() => vi.useFakeTimers())
afterEach(() => vi.useRealTimers())

describe('useAvailability (UI-FRM-9)', () => {
  it('checks about 300 ms after typing stops, and only then', async () => {
    const check = vi.fn().mockResolvedValue({ available: true, problem: null })
    const { value } = setup(check)

    await type(value, 'acme')
    await vi.advanceTimersByTimeAsync(AVAILABILITY_DELAY_MS - 1)
    expect(check).not.toHaveBeenCalled()
    await type(value, 'acme-co')
    await vi.advanceTimersByTimeAsync(AVAILABILITY_DELAY_MS)

    expect(check.mock.calls).toEqual([['acme-co']])
  })

  it.each([
    [{ available: true, problem: null }, 'Slug is available'],
    [{ available: false, problem: 'taken' }, 'Slug is taken'],
    [{ available: false, problem: 'reserved' }, 'Slug is reserved'],
    [{ available: false, problem: 'must_start_with_letter' }, 'Slug must start with a letter'],
  ])('says what the server answered: %o', async (answer, said) => {
    const { value, message } = setup(vi.fn().mockResolvedValue(answer))

    await type(value, 'acme')
    await vi.advanceTimersByTimeAsync(AVAILABILITY_DELAY_MS)

    expect(message()).toBe(said)
  })

  it('checks nothing it is told to skip, and says nothing', async () => {
    const check = vi.fn()
    const { value, message } = setup(check, (v) => v === 'mine')

    await type(value, 'mine')
    await vi.advanceTimersByTimeAsync(AVAILABILITY_DELAY_MS)

    expect(check).not.toHaveBeenCalled()
    expect(message()).toBe('')
  })

  it('drops an answer that arrives after the value changed', async () => {
    let answer!: (value: Answer) => void
    const check = vi.fn().mockReturnValueOnce(new Promise<Answer>((r) => (answer = r)))
    const { value, message } = setup(check)
    await type(value, 'acme')
    await vi.advanceTimersByTimeAsync(AVAILABILITY_DELAY_MS)

    await type(value, '')
    answer({ available: false, problem: 'taken' })
    await vi.advanceTimersByTimeAsync(0)

    expect(message()).toBe('')
  })

  it('says nothing when the check fails', async () => {
    const failure = new ApiError(503, { code: 'network_error', message: '', details: {} })
    const { value, message } = setup(vi.fn().mockRejectedValue(failure))

    await type(value, 'acme')
    await vi.advanceTimersByTimeAsync(AVAILABILITY_DELAY_MS)

    expect(message()).toBe('')
  })
})
