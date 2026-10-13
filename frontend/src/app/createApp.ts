/**
 * The app, with Pinia, the router, PrimeVue, and the session handling wired up. `main.ts` mounts
 * it; tests build it the same way.
 */
import { createPinia } from 'pinia'
import PrimeVue from 'primevue/config'
import { createApp } from 'vue'
import type { RouterHistory } from 'vue-router'

import { onSessionProblem } from '@/api/client'
import App from '@/App.vue'

import { createAppRouter } from './router'
import { sessionProblemHandler } from './session'
import { theme } from './theme/preset'

export function createWaterlineApp(history?: RouterHistory) {
  const app = createApp(App)
  const pinia = createPinia()
  // Pinia first: the router's guard reads the current-user store on the first navigation.
  app.use(pinia)
  const router = createAppRouter(history)
  app.use(router)
  app.use(PrimeVue, { theme })
  onSessionProblem(sessionProblemHandler(router))
  return { app, pinia, router }
}
