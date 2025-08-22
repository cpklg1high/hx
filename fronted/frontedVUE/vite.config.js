import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import AutoImport from 'unplugin-auto-import/vite'
import Components from 'unplugin-vue-components/vite'
import { ElementPlusResolver } from 'unplugin-vue-components/resolvers'

export default defineConfig({
  plugins: [vue()],
  server:{
    port:5173,
    open:true,
    proxy: {
      // 统一把 /api 前缀的请求转发到后端
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        // 保持路径为 /api/...，后端 urls.py 记得以 /api 起始
      }
    }
  },
  plugins: [
    vue(),
    AutoImport({
      resolvers: [ElementPlusResolver()],
      dts: false,
    }),
    Components({
      resolvers: [ElementPlusResolver()],
      dts: false,
    })
  ]
})
