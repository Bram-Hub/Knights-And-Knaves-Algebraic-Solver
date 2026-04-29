import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  // Custom domain (kkas.bram-hub.com) serves from root — no subpath needed
  base: '/',
  server: {
    proxy: {
      '/api': 'http://localhost:8000',
    },
  },
})
