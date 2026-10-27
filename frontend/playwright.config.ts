import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './e2e',
  testMatch: ['**/journey.pw.ts', '**/mode-gating.pw.ts'],
  use: {
    baseURL: 'http://127.0.0.1:5173',
    browserName: 'chromium',
  },
  webServer: {
    command: 'corepack pnpm dev --host 127.0.0.1 --port 5173 --strictPort',
    url: 'http://127.0.0.1:5173',
    reuseExistingServer: !process.env.CI,
    env: {
      VITE_API_URL: 'http://127.0.0.1:8000',
      VITE_APP_MODE: 'local',
      VITE_OTEL_EXPORTER_OTLP_ENDPOINT:
        'http://127.0.0.1:4318/v1/traces',
    },
  },
});
