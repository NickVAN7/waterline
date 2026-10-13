import {
  createRouter,
  createWebHistory,
  type RouteRecordRaw,
  type Router,
  type RouterHistory,
} from 'vue-router'

import { authGuard } from './guards/auth'
import { installRouteFocus } from './routeFocus'
import MyWorkView from '@/views/my_work/MyWorkView.vue'

// Every top-level path segment here is on the backend's reserved-slug list (`ReservedSlug` in the
// API schema), so no org slug can take it; `/` is My work.
export const routes: RouteRecordRaw[] = [
  { path: '/', name: 'my-work', component: MyWorkView },
  {
    path: '/sign-in',
    name: 'sign-in',
    component: () => import('@/views/auth/SignInView.vue'),
    meta: { guest: true, layout: 'auth' },
  },
  {
    path: '/account/change-password',
    name: 'change-password',
    component: () => import('@/views/auth/ChangePasswordView.vue'),
    meta: { layout: 'auth' },
  },
  {
    path: '/status',
    name: 'status',
    component: () => import('@/views/status/StatusView.vue'),
    meta: { public: true },
  },
  // Last: any path no other route matches.
  {
    path: '/:pathMatch(.*)*',
    name: 'not-found',
    component: () => import('@/views/errors/NotFoundView.vue'),
  },
]

/** The app's router. Tests pass a memory history. */
export function createAppRouter(history: RouterHistory = createWebHistory()): Router {
  const router = createRouter({ history, routes })
  router.beforeEach(authGuard)
  installRouteFocus(router)
  return router
}
