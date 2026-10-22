import { defineConfig } from '@playwright/test';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';

export default defineConfig({
  testDir: './e2e', workers: 1, timeout: 30000,
  use: { launchOptions: process.env.RADAR_CHROMIUM_PATH ? { executablePath: process.env.RADAR_CHROMIUM_PATH } : {}, baseURL: 'http://127.0.0.1:5173', trace: 'retain-on-failure' },
  webServer: [
    { command: `${process.env.RADAR_TEST_PYTHON || '../.venv/bin/python'} -m uvicorn app.main:app --host 127.0.0.1 --port 18080`,
      cwd: '../backend', url: 'http://127.0.0.1:18080/openapi.json',
      env: { RADAR_V2_CONFIG: resolve('../contracts/examples/integration/config.json'), RADAR_DATABASE_URL: `sqlite:///${join(tmpdir(), `radar-browser-${process.pid}.db`)}` } },
    { command: 'npm run dev', url: 'http://127.0.0.1:5173',
      env: { RADAR_API_TARGET: 'http://127.0.0.1:18080' } },
  ],
});
