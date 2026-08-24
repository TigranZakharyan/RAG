import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: 5173,
    proxy: {
      '/auth': {
        target: process.env.VITE_API_URL || 'http://api:8000',
        changeOrigin: true,
      },
      '/users': {
        target: process.env.VITE_API_URL || 'http://api:8000',
        changeOrigin: true,
      },
      '/conversations': {
        target: process.env.VITE_API_URL || 'http://api:8000',
        changeOrigin: true,
      },
      '/files': {
        target: process.env.VITE_API_URL || 'http://api:8000',
        changeOrigin: true,
      },
      '/chat': {
        target: process.env.VITE_API_URL || 'http://api:8000',
        changeOrigin: true,
      },
    },
  },
})


