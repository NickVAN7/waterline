import { fileURLToPath } from 'node:url'

import { configDefaults, defineConfig, mergeConfig } from 'vitest/config'

import viteConfig from './vite.config.ts'

// Coverage gates: docs/testing-strategy.md, "Coverage gates".
const STRICT = { lines: 90 }

export default mergeConfig(
  viteConfig,
  defineConfig({
    test: {
      environment: 'jsdom',
      include: ['src/**/*.spec.ts'],
      exclude: [...configDefaults.exclude, 'e2e/**'],
      root: fileURLToPath(new URL('./', import.meta.url)),
      restoreMocks: true,
      coverage: {
        provider: 'v8',
        include: ['src/**/*.{ts,vue}'],
        exclude: [
          '**/*.spec.ts',
          // Generated types only: no runtime code to cover.
          'src/api/schema.d.ts',
          // Bootstrap that mounts the app into index.html; everything it wires up is tested
          // through the router and the layout.
          'src/main.ts',
        ],
        thresholds: {
          lines: 80,
          'src/composables/**': STRICT,
          'src/stores/**': STRICT,
          'src/app/guards/**': STRICT,
        },
      },
    },
  }),
)
