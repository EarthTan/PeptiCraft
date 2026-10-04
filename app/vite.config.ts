import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      '@': import.meta.dirname + '/src',
    },
  },
  // 本地调试用：固定 127.0.0.1:5173，端口被占用时直接报错而不是悄悄换端口
  server: {
    host: '127.0.0.1',
    port: 5173,
    strictPort: true,
    // 开发期把 /api 转发到后端服务，浏览器始终只面对一个来源。
    // 后端地址可用 VITE_API_PROXY_TARGET 覆盖（例如指向另一台机器上的服务）。
    proxy: {
      '/api': {
        target: process.env.VITE_API_PROXY_TARGET ?? 'http://127.0.0.1:8000',
        changeOrigin: false,
      },
    },
  },
})
