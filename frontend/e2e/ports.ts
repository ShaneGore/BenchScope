function port(name: string, fallback: number): number {
  const raw = process.env[name] ?? String(fallback);
  if (!/^\d+$/.test(raw) || Number(raw) < 1 || Number(raw) > 65535) {
    throw new Error(`${name} must be a TCP port between 1 and 65535.`);
  }
  return Number(raw);
}

export const apiPort = port('E2E_API_PORT', 8000);
export const jwksPort = port('E2E_JWKS_PORT', 8001);
export const frontendPort = port('E2E_FRONTEND_PORT', 5173);
export const demoPort = port('E2E_DEMO_PORT', 5174);
export const previewPort = port('E2E_PREVIEW_PORT', 5175);
export const apiOrigin = `http://127.0.0.1:${apiPort}`;
export const jwksOrigin = `http://127.0.0.1:${jwksPort}`;
export const frontendOrigin = `http://127.0.0.1:${frontendPort}`;
export const demoOrigin = `http://127.0.0.1:${demoPort}`;
export const previewOrigin = `http://127.0.0.1:${previewPort}`;
