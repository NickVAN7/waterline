import { createPinia } from 'pinia'
import { createApp } from 'vue'

import App from './App.vue'
import { createAppRouter } from './app/router'
import './app/styles.css'

createApp(App).use(createPinia()).use(createAppRouter()).mount('#app')
