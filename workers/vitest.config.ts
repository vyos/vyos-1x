import { defineConfig } from "vitest/config";
import { cloudflareTest } from "@cloudflare/vitest-pool-workers";

export default defineConfig({
  plugins: [
    // Each suite provides its own wrangler config via miniflare option overrides;
    // apex tests read workers/apex/wrangler.jsonc to assert config congruence.
    cloudflareTest({
      miniflare: {
        compatibilityDate: "2026-07-01",
      },
    }),
  ],
});
