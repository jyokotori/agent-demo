import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig(() => {
  const apiProxyTarget = process.env.VITE_DEV_API_PROXY_TARGET ?? 'http://127.0.0.1:8000';

  return {
    plugins: [react()],
    server: {
      port: 5173,
      host: true,
      proxy: {
        '/api': {
          target: apiProxyTarget,
          changeOrigin: true,
          secure: false
        }
      }
    }
  };
});
