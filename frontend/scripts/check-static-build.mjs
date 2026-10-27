import { existsSync, readFileSync, readdirSync } from 'node:fs';
import { join } from 'node:path';

const outputDir = process.argv[2] ?? 'dist-pages';
const configuredBase = process.env.VITE_BASE_PATH;
const apiUrl = process.env.VITE_API_URL;

if (!configuredBase || configuredBase === '/') {
  throw new Error('VITE_BASE_PATH must be a non-root path for this check');
}
if (!apiUrl || !['http:', 'https:'].includes(new URL(apiUrl).protocol)) {
  throw new Error('VITE_API_URL must be an absolute HTTP(S) URL for this check');
}

const basePath = `/${configuredBase.split('/').filter(Boolean).join('/')}/`;
const html = readFileSync(join(outputDir, 'index.html'), 'utf8');
const assetUrls = [...html.matchAll(/(?:src|href)="([^"]+)"/g)]
  .map((match) => match[1])
  .filter((url) => url.startsWith(`${basePath}assets/`));

if (assetUrls.length === 0) {
  throw new Error(`No assets in index.html use the configured base ${basePath}`);
}
for (const url of assetUrls) {
  if (!existsSync(join(outputDir, url.slice(basePath.length)))) {
    throw new Error(`Configured asset is missing: ${url}`);
  }
}

const assets = join(outputDir, 'assets');
const bundles = readdirSync(assets).filter((file) => file.endsWith('.js'));
if (
  !bundles.length ||
  !bundles.some((file) => readFileSync(join(assets, file), 'utf8').includes(apiUrl))
) {
  throw new Error('The static bundle does not contain the separately configured API URL');
}

console.log(`Verified ${assetUrls.length} base-prefixed assets and API URL ${new URL(apiUrl).origin}`);
