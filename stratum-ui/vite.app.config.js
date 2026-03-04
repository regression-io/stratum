import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { resolve } from 'path'

// Builds the standalone stratum-ui app into dist/app/
// Entry: src/app/index.html → dist/app/index.html
export default defineConfig({
  plugins: [react()],
  root: resolve(__dirname, 'src/app'),
  build: {
    outDir: resolve(__dirname, 'dist/app'),
    emptyOutDir: true,
  },
})
