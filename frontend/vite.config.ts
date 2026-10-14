import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
      '/health': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/extract': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/extract-and-align': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})
