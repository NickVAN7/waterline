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
// API schema), so no org slug can take it; `/` is My work, and `/:orgSlug` is an org's pages
// (router.spec.ts checks it).
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
    path: '/account',
    name: 'account',
    component: () => import('@/views/user/AccountView.vue'),
  },
  {
    path: '/account/no-access',
    name: 'no-access',
    component: () => import('@/views/errors/NoAccessView.vue'),
    meta: { layout: 'auth' },
  },
  // Workspace administration (UI-SHL-10, DL-104): every page is for its owners, admins, and system
  // admins; anyone else gets the not-found page from the API's 404.
  { path: '/workspace', redirect: { name: 'workspace-staff' } },
  {
    path: '/workspace/staff',
    name: 'workspace-staff',
    component: () => import('@/views/workspace/StaffView.vue'),
  },
  {
    path: '/workspace/orgs',
    name: 'workspace-orgs',
    component: () => import('@/views/workspace/OrgsView.vue'),
  },
  {
    path: '/workspace/users',
    name: 'workspace-users',
    component: () => import('@/views/workspace/UsersView.vue'),
  },
  {
    path: '/workspace/users/:userId/access',
    name: 'user-access',
    component: () => import('@/views/user/AccessReviewView.vue'),
  },
  {
    path: '/workspace/settings',
    name: 'workspace-settings',
    component: () => import('@/views/workspace/WorkspaceSettingsView.vue'),
  },
  // Org administration (UI-SHL-10, DL-104): for its owners and admins, and workspace admins.
  {
    path: '/:orgSlug/members',
    name: 'org-members',
    component: () => import('@/views/org/OrgMembersView.vue'),
  },
  {
    path: '/:orgSlug/settings',
    name: 'org-settings',
    component: () => import('@/views/org/OrgSettingsView.vue'),
  },
  {
    path: '/:orgSlug/projects',
    name: 'org-projects',
    component: () => import('@/views/project/OrgProjectsView.vue'),
  },
  {
    path: '/:orgSlug/projects/:key',
    name: 'project-home',
    component: () => import('@/views/project/ProjectHomeView.vue'),
    meta: { settlesItself: true },
  },
  {
    path: '/:orgSlug/projects/:key/members',
    name: 'project-members',
    component: () => import('@/views/project/ProjectMembersView.vue'),
    meta: { settlesItself: true },
  },
  {
    path: '/:orgSlug/projects/:key/access',
    name: 'project-access',
    component: () => import('@/views/project/ProjectAccessView.vue'),
    meta: { settlesItself: true },
  },
  {
    path: '/:orgSlug/projects/:key/settings',
    name: 'project-settings',
    component: () => import('@/views/project/ProjectSettingsView.vue'),
    meta: { settlesItself: true },
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
