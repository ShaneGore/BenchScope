import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './e2e',
  testMatch: '**/demo.pw.ts',
  use: {
    baseURL: 'http://127.0.0.1:5174',
    browserName: 'chromium',
  },
  webServer: {
    command: 'corepack pnpm dev --host 127.0.0.1 --port 5174 --strictPort',
    url: 'http://127.0.0.1:5174',
    reuseExistingServer: !process.env.CI,
    env: {
      VITE_API_URL: 'http://127.0.0.1:8000',
      VITE_APP_MODE: 'demo',
    },
  },
});
