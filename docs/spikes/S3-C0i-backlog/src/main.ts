// ?w=svar|prime picks the widget, ?theme=dark the theme, ?deny=1 makes the mock server refuse
// every move, ?rows=2000 sets the size (500 by default).
import '@/app/styles/main.css'
// SVAR's own styles, its core's included; our mapping (UI-SVR-3) after them.
import '@svar-ui/vue-grid/all.css'
import '../../../ui/svar-theme.css'

import { definePreset } from '@primeuix/themes'
import PrimeVue from 'primevue/config'
import { createApp } from 'vue'

import { theme } from '@/app/theme/preset'

import App from './App.vue'

const params = new URLSearchParams(location.search)
document.documentElement.dataset.theme = params.get('theme') === 'dark' ? 'dark' : 'light'
// ?fix=1, with ?w=prime: Aura draws DataTable's borders from its own zinc scale in dark mode; one
// mapping points it at ours (as TreeTable's, S2-C0b).
const fixed = {
  ...theme,
  preset: definePreset(theme.preset, {
    components: { datatable: { root: { borderColor: 'var(--color-border-subtle)' } } },
  }),
}
createApp(App)
  .use(PrimeVue, {
    theme: params.get('fix') === '1' ? fixed : theme,
    license: import.meta.env.VITE_PRIMEUI_LICENSE,
  })
  .mount('#app')
