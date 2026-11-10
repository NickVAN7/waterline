import { fileURLToPath, URL } from 'node:url'

import tailwindcss from '@tailwindcss/vite'
import vue from '@vitejs/plugin-vue'
import { defineConfig } from 'vite'

// The app's own tokens, styles, and PrimeVue preset are imported from frontend/src, so the
// spike measures the real theme; one copy of each library, from this folder.
export default defineConfig({
  plugins: [vue(), tailwindcss()],
  resolve: {
    alias: { '@': fileURLToPath(new URL('../../../frontend/src', import.meta.url)) },
    dedupe: ['vue', 'primevue', '@primeuix/themes', '@primeuix/styled'],
  },
  server: { fs: { allow: ['../../..'] } },
})
