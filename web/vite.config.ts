import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// Фронт и /api должны быть на одном адресе: core ставит cookie сессии
// и после входа возвращает браузер на SHTAB_PUBLIC_URL (http://localhost:3000).
export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    strictPort: true,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: false,
      },
      '/mcp/': 'http://localhost:8000',
    },
  },
})
