import { defineConfig, devices } from '@playwright/test';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const rootDir = path.resolve(__dirname, '..');
const venvPython = path.join(rootDir, '.venv', 'Scripts', 'python.exe');

export default defineConfig({
  testDir: './tests/e2e',
  fullyParallel: false,
  retries: 0,
  workers: 1,
  timeout: 60000,
  reporter: 'list',
  use: {
    baseURL: 'http://127.0.0.1:5173',
    trace: 'on-first-retry',
    headless: true,
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
  webServer: [
    {
      command: `"${venvPython}" -m uvicorn backend.main:app --host 127.0.0.1 --port 8000`,
      cwd: rootDir,
      url: 'http://127.0.0.1:8000/api/health',
      reuseExistingServer: true,
      timeout: 60000,
    },
    {
      command: 'npm.cmd run dev',
      cwd: __dirname,
      url: 'http://127.0.0.1:5173',
      reuseExistingServer: true,
      timeout: 60000,
    },
  ],
});
