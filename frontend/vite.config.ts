import { fileURLToPath, URL } from 'node:url'

import vue from '@vitejs/plugin-vue'
import { defineConfig } from 'vite'

// The browser only ever talks to Vite, which forwards /api to the backend, so the app and the API
// share one origin (build-plan.md, "Docker Compose"). Compose points this at the api service.
const apiProxyTarget = process.env.API_PROXY_TARGET ?? 'http://localhost:8000'

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    port: 5173,
    strictPort: true,
    // No CORS headers or preflight answers from Vite: the API alone decides cross-origin
    // behaviour (the Slice 1 Origin check), and the app never needs it.
    cors: false,
    proxy: {
      // changeOrigin stays false: the API sees the browser's own Host and Origin headers.
      '/api': { target: apiProxyTarget },
    },
  },
})
