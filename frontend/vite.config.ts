import { fileURLToPath, URL } from 'node:url'

import tailwindcss from '@tailwindcss/vite'
import vue from '@vitejs/plugin-vue'
import { defineConfig } from 'vite'

// The browser only ever talks to Vite, which forwards /api to the backend, so the app and the API
// share one origin (build-plan.md, "Docker Compose"). Compose points this at the api service.
const apiProxyTarget = process.env.API_PROXY_TARGET ?? 'http://localhost:8000'

// The Content-Security-Policy, the second layer behind MarkdownView's sanitizer (design-doc §4,
// DL-142): scripts only from our own origin. Inline styles are allowed because PrimeVue and Vite
// inject <style> tags and this server can't mint a per-response nonce (DL-246, TD-87).
const contentSecurityPolicy = [
  "default-src 'self'",
  "script-src 'self'",
  "style-src 'self' 'unsafe-inline'",
  "object-src 'none'",
  "base-uri 'self'",
  "form-action 'self'",
  "frame-ancestors 'none'",
].join('; ')

export default defineConfig({
  plugins: [vue(), tailwindcss()],
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
    headers: { 'Content-Security-Policy': contentSecurityPolicy },
    proxy: {
      // changeOrigin stays false: the API sees the browser's own Host and Origin headers.
      '/api': { target: apiProxyTarget },
    },
  },
})
