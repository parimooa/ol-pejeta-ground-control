/**
 * main.js
 *
 * Bootstraps Vuetify and other plugins then mounts the App`
 */

// Plugins
// import { registerPlugins } from '@/plugins'
//
// // Components
// import App from './App.vue'
//
// // Composables
// import { createApp } from 'vue'
//
// // Styles
// import 'unfonts.css'
//
// const app = createApp(App)
//
// registerPlugins(app)

// import App from "@/App.vue";

// app.mount('#app')
import { createApp } from 'vue'
import App from './App.vue'
// Vuetify
import 'vuetify/styles'
import { createVuetify } from 'vuetify'
import * as components from 'vuetify/components'
import * as directives from 'vuetify/directives'
import { mdi } from 'vuetify/iconsets/mdi'
import '@mdi/font/css/materialdesignicons.css'

const vuetify = createVuetify({
  components,
  directives,
  icons: {
    defaultSet: 'mdi',
    sets: {
      mdi,
    },
  },
  theme: {
    defaultTheme: 'light',
  },
})

const app = createApp(App)
app.use(vuetify)
app.mount('#app')
