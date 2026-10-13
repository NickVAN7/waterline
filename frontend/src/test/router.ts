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
    ],
  })
  await router.push(path)
  return router
}
