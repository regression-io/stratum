import react from '@vitejs/plugin-react'
import path from 'node:path'
import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: 5195,
    proxy: {
      '/api': 'http://localhost:3001',
      // Only proxy file-watcher and vision WS — terminal connects directly to port 3002
      '/ws/files': { target: 'ws://localhost:3001', ws: true },
      '/ws/vision': { target: 'ws://localhost:3001', ws: true },
    },
  },
});
