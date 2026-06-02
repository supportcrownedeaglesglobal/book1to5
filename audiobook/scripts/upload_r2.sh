#!/usr/bin/env bash
# upload_r2.sh — Upload the mastered audiobook MP3s to Cloudflare R2 with
# long-lived, immutable caching so repeat plays are served from Cloudflare's
# edge (free, no R2 egress/Class-B billing).
#
# Prereqs:
#   1. rclone installed (choco install rclone) and configured with an R2 remote
#      named "r2"  (run: rclone config  -> type "Cloudflare R2" -> paste your
#      Access Key ID / Secret / account endpoint from R2 > Manage API Tokens).
#   2. A bucket created in R2.
#
# Usage:
#   BUCKET=book5-audio bash audiobook/scripts/upload_r2.sh
#
# The files land at  r2:<BUCKET>/audio/book-5/<id>.mp3  so that, with
#   AUDIO_BASE_URL = "https://<your-r2-custom-domain>"  in index.html,
# each track resolves to  https://<your-r2-custom-domain>/audio/book-5/<id>.mp3
set -euo pipefail
: "${BUCKET:?set BUCKET to your R2 bucket name, e.g. BUCKET=book5-audio}"
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"

rclone copy "$ROOT/audio/book-5" "r2:${BUCKET}/audio/book-5" \
  --include "*.mp3" \
  --header-upload "Cache-Control: public, max-age=31536000, immutable" \
  --transfers 16 --checkers 16 --progress

echo
echo "Done. Verify caching: load a track twice and check the response header"
echo "  cf-cache-status: MISS  (first load) -> HIT (subsequent loads = edge-cached, no R2 cost)"
echo "IMPORTANT: caching only works through a CUSTOM DOMAIN. The pub-*.r2.dev dev URL does NOT cache."
echo
echo "wrangler alternative (per file):"
echo "  wrangler r2 object put \"${BUCKET}/audio/book-5/<id>.mp3\" --file=path/to/<id>.mp3 \\"
echo "    --cache-control \"public, max-age=31536000, immutable\""
