/** A router with the app's route names, for mounting one view in a component test. */
import { createMemoryHistory, createRouter } from 'vue-router'

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
      { path: '/account', name: 'account', component: Page },
      { path: '/account/no-access', name: 'no-access', component: Page },
      { path: '/workspace/staff', name: 'workspace-staff', component: Page },
      { path: '/workspace/orgs', name: 'workspace-orgs', component: Page },
      { path: '/workspace/users', name: 'workspace-users', component: Page },
      { path: '/workspace/users/:userId/access', name: 'user-access', component: Page },
      { path: '/workspace/settings', name: 'workspace-settings', component: Page },
      { path: '/:orgSlug/members', name: 'org-members', component: Page },
      { path: '/:orgSlug/settings', name: 'org-settings', component: Page },
      { path: '/:orgSlug/projects', name: 'org-projects', component: Page },
      { path: '/:orgSlug/projects/:key', name: 'project-home', component: Page },
    ],
  })
  await router.push(path)
  return router
}
