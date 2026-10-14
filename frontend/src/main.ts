import { createWaterlineApp } from './app/createApp'
import './app/styles/main.css'
import { applyStoredTheme } from './composables/useTheme'

applyStoredTheme()
createWaterlineApp().app.mount('#app')
