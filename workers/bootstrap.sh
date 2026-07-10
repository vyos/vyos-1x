#!/usr/bin/env bash
# One-time bootstrap: deploy placeholder versions of every service-binding
# target so the apex Worker (whose config binds all of them) can deploy.
# Requires CLOUDFLARE_API_TOKEN + CLOUDFLARE_ACCOUNT_ID in the environment.
set -euo pipefail
cd "$(dirname "$0")"

mkdir -p ../dist/assets
for slug in rolling 1.5 1.4 1.3 1.2; do
  mkdir -p "../dist/assets/en/$slug"
  printf '<html><body>bootstrap placeholder — real build pending</body></html>' \
    > "../dist/assets/en/$slug/index.html"
done

deploy() { # config-suffix worker-name
  for suffix in "" "-candidate"; do
    npx wrangler deploy --config "branch/wrangler.$1.jsonc" \
      --name "$2$suffix" \
      --var DOCS_BUILD_SHA:bootstrap \
      --var DOCS_ENV:$( [ -n "$suffix" ] && echo canary || echo production )
  done
}

npm ci
deploy rolling vyos-docs-rolling-en
deploy v15     vyos-docs-v15-en
deploy v14     vyos-docs-v14-en
deploy legacy  vyos-docs-legacy
echo "bootstrap complete — all 8 binding targets exist; apex can now deploy"
