import { defineConfig } from 'vite';

export default defineConfig({
  preview: { proxy: { '/api': 'http://127.0.0.1:8000' } },
  server: { proxy: { '/api': { target: process.env.RADAR_API_TARGET || 'http://127.0.0.1:8000', changeOrigin: true } } },
});
