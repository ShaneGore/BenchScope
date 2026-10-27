import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './e2e',
  testMatch: '**/base-path.pw.ts',
  use: {
    baseURL: 'http://127.0.0.1:5175/benchscope/',
    browserName: 'chromium',
  },
  webServer: {
    command:
      'corepack pnpm build && corepack pnpm exec vite preview --host 127.0.0.1 --port 5175 --strictPort',
    url: 'http://127.0.0.1:5175/benchscope/',
    reuseExistingServer: false,
    env: {
      VITE_APP_MODE: 'demo',
      VITE_API_URL: 'http://127.0.0.1:8000',
      VITE_BASE_PATH: '/benchscope/',
    },
  },
});
