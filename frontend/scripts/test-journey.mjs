import { spawnSync } from 'node:child_process';
import { randomUUID } from 'node:crypto';
import { rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';

const cli = fileURLToPath(
  new URL('../node_modules/@playwright/test/cli.js', import.meta.url)
);
const runId = randomUUID();
const env = {
  ...process.env,
  E2E_RUN_ID: runId,
  E2E_SCHEMA: `benchscope_e2e_${runId.replaceAll('-', '').slice(0, 16)}`,
  E2E_STATE_FILE: join(tmpdir(), `benchscope-e2e-${runId}.json`),
};
const outputDir = join(tmpdir(), `benchscope-playwright-${runId}`);

const configs = [
  'playwright.config.ts',
  'playwright.demo.config.ts',
  'playwright.base.config.ts',
];

try {
  for (const [index, config] of configs.entries()) {
    const result = spawnSync(
      process.execPath,
      [cli, 'test', '--config', config, '--output', outputDir],
      { env, stdio: 'inherit' }
    );
    const cleanup =
      index < 2
        ? spawnSync(
            'uv',
            [
              'run',
              '--directory',
              '../backend',
              'python',
              'tests/e2e_server.py',
              'cleanup',
            ],
            { env: { ...env, PYTHONPATH: '.' }, stdio: 'inherit' }
          )
        : undefined;
    if (result.error) throw result.error;
    if (cleanup?.error) throw cleanup.error;
    if (result.status !== 0) {
      process.exitCode = result.status ?? 1;
      break;
    }
    if (cleanup && cleanup.status !== 0) {
      process.exitCode = cleanup.status ?? 1;
      break;
    }
  }
} finally {
  rmSync(outputDir, { recursive: true, force: true });
}
