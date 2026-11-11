import { defineConfig } from '@playwright/test';
export default defineConfig({
  testDir: './e2e', testMatch: 'pilot.spec.js', workers: 1,
  use: { baseURL: 'http://127.0.0.1:5178', launchOptions: process.env.RADAR_CHROMIUM_PATH ? { executablePath: process.env.RADAR_CHROMIUM_PATH } : {} },
  webServer: { command: 'npx vite --host 127.0.0.1 --port 5178 --strictPort', url: 'http://127.0.0.1:5178' },
});
