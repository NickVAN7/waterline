import { afterEach, describe, expect, it } from 'vitest'

import { ApiError } from '@/api/client'

import { useLoad } from './useLoad'

const FAILURE = new ApiError(503, { code: 'network_error', message: '', details: {} })

afterEach(() => {
  document.body.innerHTML = ''
})

describe('useLoad', () => {
  it('keeps the data and reports the load as done', async () => {
    const load = useLoad(() => Promise.resolve('data'))

    expect(await load.run()).toBe(true)

    expect(load.data.value).toBe('data')
    expect(load.error.value).toBeUndefined()
    expect(load.loading.value).toBe(false)
  })

  it('is loading while the request runs', () => {
    const load = useLoad(() => new Promise(() => {}))

    void load.run()

    expect(load.loading.value).toBe(true)
  })

  it('keeps an API failure for the error state', async () => {
    const load = useLoad(() => Promise.reject(FAILURE))

    expect(await load.run()).toBe(false)

    expect(load.error.value).toBe(FAILURE)
    expect(load.loading.value).toBe(false)
  })

  it('keeps the latest request, dropping an older answer that arrives late', async () => {
    const answers: ((value: string) => void)[] = []
    const load = useLoad(() => new Promise<string>((resolve) => answers.push(resolve)))
    const first = load.run()
    const second = load.run()

    answers[1]!('page 3')
    await second
    expect(load.loading.value).toBe(false)
    answers[0]!('page 2')
    await first

    expect(load.data.value).toBe('page 3')
  })

  it('is still loading while a newer request runs after an older one ends', async () => {
    const answers: ((value: string) => void)[] = []
    const load = useLoad(() => new Promise<string>((resolve) => answers.push(resolve)))
    const first = load.run()
    void load.run()

    answers[0]!('page 2')
    await first

    expect(load.loading.value).toBe(true)
    expect(load.data.value).toBeUndefined()
  })

  it('lets anything else through, as a bug', async () => {
    const load = useLoad(() => Promise.reject(new TypeError('bug')))

    await expect(load.run()).rejects.toThrow('bug')
  })

  it('moves focus to the h1 when Try again succeeds, and clears the error', async () => {
    document.body.innerHTML = '<main><h1>My work</h1></main>'
    let fail = true
    const load = useLoad(() => (fail ? Promise.reject(FAILURE) : Promise.resolve('data')))
    await load.run()
    fail = false

    await load.retry()

    expect(load.error.value).toBeUndefined()
    expect(document.activeElement).toBe(document.querySelector('h1'))
  })

  it('leaves focus where it is when Try again fails again', async () => {
    document.body.innerHTML = '<main><h1>My work</h1></main><button>Try again</button>'
    const button = document.querySelector('button')!
    button.focus()
    const load = useLoad(() => Promise.reject(FAILURE))

    await load.retry()

    expect(document.activeElement).toBe(button)
  })
})
