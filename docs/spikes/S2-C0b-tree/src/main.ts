// ?w=svar|prime picks the widget, ?theme=dark the theme, ?deny=1 makes the mock server refuse moves,
// ?fix=1 adds the wrapper fixes this spike found for TreeTable (results.md), ?rows=2000 and
// ?open=none set the size and the starting state, and ?rebuild=1 rebuilds TreeTable's nodes on a move.
import '@/app/styles/main.css'
import '../../../ui/svar-theme.css'

import { definePreset } from '@primeuix/themes'
import PrimeVue from 'primevue/config'
import { createApp } from 'vue'

import { theme } from '@/app/theme/preset'

import App from './App.vue'

const params = new URLSearchParams(location.search)
document.documentElement.dataset.theme = params.get('theme') === 'dark' ? 'dark' : 'light'
// Aura draws TreeTable's borders from its own zinc scale in dark mode; one mapping points it at ours.
const fixed = {
  ...theme,
  preset: definePreset(theme.preset, {
    components: { treetable: { root: { borderColor: 'var(--color-border-subtle)' } } },
  }),
}
createApp(App)
  .use(PrimeVue, { theme: params.get('fix') === '1' ? fixed : theme })
  .mount('#app')
