import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// 开发期把 /api 代理到本地 FastAPI 后端，前端代码不写死后端地址
// base 同理可配：GitHub Pages 发布子路径时构建前设 VITE_BASE=/zhixue-ark/
export default defineConfig({
  base: process.env.VITE_BASE || '/',
  plugins: [vue()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true
      }
    }
  }
})
