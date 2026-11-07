import { apiPort, apiOrigin, demoPort, demoOrigin } from './e2e/ports';
import { defineConfig } from '@playwright/test';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

if (!process.env.TEST_DATABASE_URL) {
  throw new Error('Set TEST_DATABASE_URL to a local PostgreSQL test database.');
}
if (!process.env.E2E_RUN_ID) {
  throw new Error('Run journeys with pnpm test:journey to create an isolated run ID.');
}

const runId = process.env.E2E_RUN_ID;
const schema = `benchscope_e2e_${runId.replaceAll('-', '').slice(0, 16)}`;
const stateFile = join(tmpdir(), `benchscope-e2e-${runId}.json`);
process.env.E2E_SCHEMA = schema;
process.env.E2E_STATE_FILE = stateFile;

export default defineConfig({
  testDir: './e2e',
  testMatch: '**/demo.pw.ts',
  workers: 1,
  use: {
    baseURL: demoOrigin,
    browserName: 'chromium',
  },
  webServer: [
    {
      command: 'uv run python tests/e2e_server.py',
      cwd: '../backend',
      url: `${apiOrigin}/health`,
      reuseExistingServer: false,
      env: {
        APP_MODE: 'hosted',
        APP_ENV: 'test',
        LOCAL_AUTH_BYPASS: 'false',
        HOST: '127.0.0.1',
        PORT: String(apiPort),
        BENCHMARK_ENABLED: 'false',
        CORS_ORIGINS: JSON.stringify([demoOrigin]),
        DATABASE_URL: '',
        CLERK_JWKS_URL: 'https://clerk.example.invalid/.well-known/jwks.json',
        CLERK_ISSUER: 'https://clerk.example.invalid',
        CLERK_AUTHORIZED_PARTIES: JSON.stringify([demoOrigin]),
        TEST_DATABASE_URL: process.env.TEST_DATABASE_URL,
        PYTHONPATH: '.',
        E2E_SCHEMA: schema,
        E2E_STATE_FILE: stateFile,
      },
    },
    {
      command: `corepack pnpm dev --host 127.0.0.1 --port ${demoPort} --strictPort`,
      url: demoOrigin,
      reuseExistingServer: false,
      env: {
        E2E_CLERK_STUB: 'true',
        VITE_API_URL: apiOrigin,
        VITE_APP_MODE: 'hosted',
        VITE_CLERK_PUBLISHABLE_KEY: 'pk_test_benchscope.example.invalid',
      },
    },
  ],
});
