import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  // relative asset paths so the build works from any sub-path (GitHub Pages /Ditto/tito/)
  base: './',
  build: {
    // build straight into the website: docs/tito → served as /Ditto/tito/
    outDir: '../docs/tito',
    emptyOutDir: true,
  },
  server: { port: 5173, host: true },
})
