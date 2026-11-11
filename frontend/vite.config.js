import { mcpAutoPlugin } from './src/mcpAutoPlugin.js';
import { defineConfig } from 'vite';

export default defineConfig({
  plugins: [mcpAutoPlugin()],
  preview: { proxy: { '/api': 'http://127.0.0.1:8000' } },
  server: { proxy: { '/ocr-api': { target: 'http://127.0.0.1:8765', rewrite: path => path.replace(/^\/ocr-api/, '') }, '/api': { target: process.env.RADAR_API_TARGET || 'http://127.0.0.1:8000', changeOrigin: true } } },
});
