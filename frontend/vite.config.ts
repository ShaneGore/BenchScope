import react from "@vitejs/plugin-react";
import { fileURLToPath } from "node:url";
import { defineConfig } from "vitest/config";

const aliases = {
  "@": "/src",
  ...(process.env.E2E_CLERK_STUB === 'true'
    ? {
        "@clerk/react": fileURLToPath(
          new URL('./e2e/clerk-stub.tsx', import.meta.url)
        ),
      }
    : {}),
};

export default defineConfig({
  base: process.env.VITE_BASE_PATH || '/',
  plugins: [react()],
  resolve: { alias: aliases },
  test: {
    environment: "jsdom",
  },
});
