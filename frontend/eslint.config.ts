import pluginVitest from '@vitest/eslint-plugin'
import { defineConfigWithVueTs, vueTsConfigs } from '@vue/eslint-config-typescript'
import skipFormatting from 'eslint-config-prettier/flat'
import { globalIgnores } from 'eslint/config'
import pluginVue from 'eslint-plugin-vue'

export default defineConfigWithVueTs(
  {
    name: 'app/files-to-lint',
    files: ['**/*.{vue,ts,mts,tsx}'],
  },

  globalIgnores(['**/dist/**', '**/coverage/**', 'src/api/schema.d.ts']),

  ...pluginVue.configs['flat/recommended'],
  vueTsConfigs.recommended,

  // All API calls go through the generated client (frontend/CLAUDE.md).
  {
    name: 'app/api-through-the-client',
    files: ['src/**/*.{vue,ts}'],
    ignores: ['src/api/**', 'src/**/*.spec.ts'],
    rules: {
      'no-restricted-globals': [
        'error',
        { name: 'fetch', message: 'Call the API through `@/api/client`, never fetch directly.' },
      ],
      'no-restricted-properties': [
        'error',
        ...['window', 'globalThis', 'self'].map((object) => ({
          object,
          property: 'fetch',
          message: 'Call the API through `@/api/client`, never fetch directly.',
        })),
      ],
      'no-restricted-imports': [
        'error',
        {
          paths: [
            { name: 'openapi-fetch', message: 'Use the configured client from `@/api/client`.' },
          ],
        },
      ],
    },
  },

  {
    ...pluginVitest.configs.recommended,
    files: ['src/**/*.spec.ts'],
  },

  skipFormatting,
)
