import { createApp } from 'vue'
import App from './App.vue'
import router from './router/index.js'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import './style.css'

import { ensureCsrf } from './api/http.js'

const app = createApp(App)

app.use(createPinia())
app.use(router)
app.use(ElementPlus)

// 先确保浏览器种下 csrftoken，再挂载应用，避免首个刷新请求因 CSRF 缺失失败
ensureCsrf().finally(() => {
  app.mount('#app')
})
