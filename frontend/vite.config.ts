/// <reference types="vitest" />
import { defineConfig } from 'vitest/config'
import { loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), 'VITE_');
  // Kept server-side: browser requests still use the same-origin /api proxy.
  // This makes isolated UAT stacks deterministic instead of silently reaching
  // a separately running default backend on port 8000.
  const apiProxyTarget = env.VITE_API_PROXY_TARGET || 'http://127.0.0.1:8000';

  return {
    plugins: [react()],
    build: {
      manifest: true,
    },
    server: {
      proxy: {
        '/api/health': {
          target: apiProxyTarget,
          rewrite: (path) => path.replace(/^\/api/, ''),
        },
        '/api': apiProxyTarget,
      }
    },
    test: {
      environment: 'jsdom',
      globals: true,
    }
  };
});
