import { apiOrigin, previewPort, previewOrigin } from './e2e/ports';
import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './e2e',
  testMatch: '**/base-path.pw.ts',
  use: {
    baseURL: `${previewOrigin}/benchscope/`,
    browserName: 'chromium',
  },
  webServer: {
    command:
      `corepack pnpm build && corepack pnpm exec vite preview --host 127.0.0.1 --port ${previewPort} --strictPort`,
    url: `${previewOrigin}/benchscope/`,
    reuseExistingServer: false,
    env: {
      VITE_APP_MODE: 'demo',
      VITE_API_URL: apiOrigin,
      VITE_BASE_PATH: '/benchscope/',
    },
  },
});
