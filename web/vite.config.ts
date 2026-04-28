import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

const isStatic = process.env.VITE_STATIC === 'true'

export default defineConfig({
  plugins: [react()],
  // When building for GitHub Pages the app lives at /<repo-name>/
  base: isStatic ? '/Knights-And_Knaves_Solver/' : '/',
  server: {
    proxy: {
      '/api': 'http://localhost:8000',
    },
  },
})
