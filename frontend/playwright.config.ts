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
  testMatch: [
    '**/journey.pw.ts',
    '**/mode-gating.pw.ts',
    '**/ownership.pw.ts',
    '**/runner-lifecycle.pw.ts',
  ],
  workers: 1,
  use: {
    baseURL: 'http://127.0.0.1:5173',
    browserName: 'chromium',
  },
  webServer: [
    {
      command: 'uv run python tests/e2e_server.py',
      cwd: '../backend',
      url: 'http://127.0.0.1:8000/health',
      reuseExistingServer: false,
      env: {
        APP_MODE: 'local',
        APP_ENV: 'test',
        LOCAL_AUTH_BYPASS: 'false',
        HOST: '127.0.0.1',
        PORT: '8000',
        BENCHMARK_ENABLED: 'true',
        BENCHMARK_TIMEOUT_SECONDS: '0.25',
        CORS_ORIGINS: '["http://127.0.0.1:5173"]',
        CLERK_JWKS_URL: 'http://127.0.0.1:8001/.well-known/jwks.json',
        CLERK_ISSUER: 'https://clerk.example.invalid',
        CLERK_AUDIENCE: 'benchscope-e2e',
        TEST_DATABASE_URL: process.env.TEST_DATABASE_URL,
        PYTHONPATH: '.',
        E2E_SCHEMA: schema,
        E2E_STATE_FILE: stateFile,
      },
    },
    {
      command: 'corepack pnpm dev --host 127.0.0.1 --port 5173 --strictPort',
      url: 'http://127.0.0.1:5173',
      reuseExistingServer: false,
      env: {
        VITE_API_URL: 'http://127.0.0.1:8000',
        VITE_APP_MODE: 'local',
        VITE_OTEL_EXPORTER_OTLP_ENDPOINT:
          'http://127.0.0.1:4318/v1/traces',
      },
    },
  ],
});
