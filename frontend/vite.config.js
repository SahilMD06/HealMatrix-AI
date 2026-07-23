import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'node:path'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(process.cwd(), './src'),
    },
  },
  server: {
    port: 5173,
    host: true,
    // Windows bind-mounts into the Docker container don't reliably deliver native
    // filesystem-change events, so Vite's watcher (chokidar) never fires and the
    // dev server serves a stale bundle after host-side edits. Polling works
    // around that at the cost of a bit of CPU.
    watch: {
      usePolling: true,
      interval: 300,
    },
    proxy: {
      // Lets the dev server talk to the local FastAPI instance without CORS friction.
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/ws': {
        target: 'ws://localhost:8000',
        ws: true,
      },
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: false,
    chunkSizeWarningLimit: 900,
    rollupOptions: {
      output: {
        manualChunks: {
          react: ['react', 'react-dom', 'react-router-dom'],
          charts: ['recharts'],
          maps: ['leaflet', 'react-leaflet'],
          motion: ['framer-motion'],
        },
      },
    },
  },
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.js'],
    css: false,
    globals: false,
  },
})
