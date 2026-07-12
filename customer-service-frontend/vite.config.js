import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    host: '127.0.0.1',
    port: 5174,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:18082',
        changeOrigin: true,
      },
      '/ws': {
        target: 'ws://127.0.0.1:18082',
        changeOrigin: true,
        ws: true,
      },
      '/commerce': {
        target: 'http://111.228.53.183:18081',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/commerce/, ''),
      },
      '/health': {
        target: 'http://127.0.0.1:18082',
        changeOrigin: true,
      },
    },
  },
})
