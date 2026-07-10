import { defineWorkersConfig } from "@cloudflare/vitest-pool-workers/config";

export default defineWorkersConfig({
  test: {
    poolOptions: {
      workers: {
        // Each suite provides its own wrangler config via miniflare option overrides;
        // apex tests read workers/apex/wrangler.jsonc to assert config congruence.
        miniflare: {
          compatibilityDate: "2026-07-01",
        },
      },
    },
  },
});
