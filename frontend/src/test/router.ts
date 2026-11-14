/** A router with the app's route names, for mounting one view in a component test. */
import { createMemoryHistory, createRouter, type RouteRecordRaw } from 'vue-router'

const Page = { template: '<h1>page</h1>' }

export async function testRouter(path = '/') {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', name: 'my-work', component: Page },
      { path: '/projects', name: 'projects', component: Page },
      { path: '/sign-in', name: 'sign-in', component: Page },
      { path: '/account/change-password', name: 'change-password', component: Page },
      { path: '/status', name: 'status', component: Page },
      { path: '/docs', name: 'docs', component: Page },
      { path: '/account', name: 'account', component: Page },
      { path: '/account/password', name: 'account-password', component: Page },
      { path: '/account/no-access', name: 'no-access', component: Page },
      { path: '/workspace/staff', name: 'workspace-staff', component: Page },
      { path: '/workspace/orgs', name: 'workspace-orgs', component: Page },
      { path: '/workspace/users', name: 'workspace-users', component: Page },
      { path: '/workspace/users/:userId/access', name: 'user-access', component: Page },
      { path: '/workspace/settings', name: 'workspace-settings', component: Page },
      { path: '/:orgSlug/overview', name: 'org-overview', component: Page },
      { path: '/:orgSlug/members', name: 'org-members', component: Page },
      { path: '/:orgSlug/settings', name: 'org-settings', component: Page },
      { path: '/:orgSlug/projects', name: 'org-projects', component: Page },
      { path: '/:orgSlug/projects/:key', name: 'project-home', component: Page },
      {
        path: '/:orgSlug/projects/:key/requirements',
        name: 'project-requirements',
        component: Page,
      },
      {
        path: '/:orgSlug/projects/:key/requirements/new',
        name: 'project-requirement-new',
        component: Page,
      },
      {
        path: '/:orgSlug/projects/:key/requirements/:number',
        name: 'project-requirement',
        component: Page,
      },
      { path: '/:orgSlug/projects/:key/members', name: 'project-members', component: Page },
      { path: '/:orgSlug/projects/:key/access', name: 'project-access', component: Page },
      { path: '/:orgSlug/projects/:key/settings', name: 'project-settings', component: Page },
      { path: '/:orgSlug/projects/:key/trash', name: 'project-trash', component: Page },
    ],
  })
  await router.push(path)
  return router
}

// The pages a breadcrumb trail links to (DL-327), as placeholders: a crumb's RouterLink throws on
// a route its router doesn't have.
const TRAIL_TARGETS: Record<string, string> = {
  'org-projects': '/:orgSlug/projects',
  'project-home': '/:orgSlug/projects/:key',
  'project-requirements': '/:orgSlug/projects/:key/requirements',
  'project-requirement': '/:orgSlug/projects/:key/requirements/:number',
  'project-members': '/:orgSlug/projects/:key/members',
  'workspace-staff': '/workspace/staff',
  'workspace-users': '/workspace/users',
  account: '/account',
}

/** A spec's own routes, then a placeholder for each trail target they leave out (after them, and
 * never under a name they use: a second route with a name replaces the first). */
export function withTrailRoutes(routes: RouteRecordRaw[]): RouteRecordRaw[] {
  const named = new Set(routes.map((route) => route.name))
  return [
    ...routes,
    ...Object.entries(TRAIL_TARGETS)
      .filter(([name]) => !named.has(name))
      .map(([name, path]) => ({ path, name, component: { template: '<p />' } })),
  ]
}
