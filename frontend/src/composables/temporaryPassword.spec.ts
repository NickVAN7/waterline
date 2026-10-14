import { describe, expect, it } from 'vitest'

import { generateTemporaryPassword } from './temporaryPassword'

describe('generateTemporaryPassword', () => {
  it('is 16 characters when the policy asks for fewer', () => {
    expect(generateTemporaryPassword(8)).toHaveLength(16)
  })

  it('follows a policy minimum longer than 16', () => {
    expect(generateTemporaryPassword(20)).toHaveLength(20)
  })

  it('uses no look-alike characters (0/O, 1/l/I) and nothing but letters and digits', () => {
    const password = generateTemporaryPassword(2000)

    expect(password).toMatch(/^[A-HJ-NP-Za-km-z2-9]+$/)
  })

  it('is different each time', () => {
    expect(generateTemporaryPassword()).not.toBe(generateTemporaryPassword())
  })
})
