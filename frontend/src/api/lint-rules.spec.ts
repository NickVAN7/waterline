// @vitest-environment node
/**
 * The ESLint rules that keep every API call on the generated client (frontend/CLAUDE.md) really
 * fire, so a config change can't silently switch them off.
 */
import { ESLint } from 'eslint'
import { describe, expect, it } from 'vitest'

const eslint = new ESLint({ cwd: new URL('../..', import.meta.url).pathname })

async function ruleIds(code: string, filePath: string): Promise<string[]> {
  const [result] = await eslint.lintText(code, { filePath })
  return (result?.messages ?? []).map((message) => message.ruleId ?? 'parse-error')
}

describe('outside src/api/', () => {
  it.each([
    ['bare fetch', "export const r = fetch('/api/health')\n", 'no-restricted-globals'],
    ['window.fetch', "export const r = window.fetch('/api/health')\n", 'no-restricted-properties'],
    [
      'globalThis.fetch',
      "export const r = globalThis.fetch('/api/health')\n",
      'no-restricted-properties',
    ],
    ['self.fetch', "export const r = self.fetch('/api/health')\n", 'no-restricted-properties'],
    [
      'an openapi-fetch import',
      "import createClient from 'openapi-fetch'\nexport const c = createClient\n",
      'no-restricted-imports',
    ],
  ])('rejects %s', async (_case, code, rule) => {
    expect(await ruleIds(code, 'src/views/probe.ts')).toEqual([rule])
  })

  it('allows the configured client', async () => {
    const code =
      "import { api, client } from '@/api/client'\nexport const r = api(client.GET('/api/health'))\n"

    expect(await ruleIds(code, 'src/views/probe.ts')).toEqual([])
  })
})

it('lets src/api/ build the client on openapi-fetch', async () => {
  const code = "import createClient from 'openapi-fetch'\nexport const c = createClient\n"

  expect(await ruleIds(code, 'src/api/probe.ts')).toEqual([])
})
