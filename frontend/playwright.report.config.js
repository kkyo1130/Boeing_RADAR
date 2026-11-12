import {defineConfig} from '@playwright/test';
import {tmpdir} from 'node:os';import {join,resolve} from 'node:path';
export default defineConfig({testDir:'./e2e',testMatch:'operations.spec.js',workers:1,timeout:45000,
use:{baseURL:'http://127.0.0.1:18731',launchOptions:process.env.RADAR_CHROMIUM_PATH?{executablePath:process.env.RADAR_CHROMIUM_PATH}:{},trace:'retain-on-failure'},
webServer:[{command:'../.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 18730',cwd:'../backend',url:'http://127.0.0.1:18730/openapi.json',env:{RADAR_V2_CONFIG:resolve('../contracts/examples/integration/config.json'),RADAR_DATABASE_URL:`sqlite:///${join(tmpdir(),`radar-report-browser-${process.pid}.db`)}`}},
{command:'node node_modules/vite/bin/vite.js --host 127.0.0.1 --port 18731 --strictPort',url:'http://127.0.0.1:18731',env:{RADAR_API_TARGET:'http://127.0.0.1:18730'}}]});
