import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// DOCKER_DEV=1 (lihat docker-compose.dev.yml): polling file-watch karena
// bind mount macOS tak tembus inotify ke dalam container.
// VITE_PROXY_TARGET: target proxy /api (default localhost untuk npm run dev lokal).
const inDocker = process.env.DOCKER_DEV === '1';

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: 3000,
    strictPort: true,
    ...(inDocker ? { watch: { usePolling: true, interval: 300 } } : {}),
    proxy: {
      '/api': {
        target: process.env.VITE_PROXY_TARGET || 'http://localhost:8000',
        changeOrigin: true,
      }
    }
  }
});
