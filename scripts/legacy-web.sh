#!/usr/bin/env bash
# Serve the retired web tool (tag web-tool-final) locally at http://localhost:4173/open-book-builder/
# until the desktop app has parity. Downloads the built site from the GitHub Release on first run.
set -euo pipefail
DIR="${LEGACY_WEB_DIR:-/data/checkouts/open-book-builder-web-final}"
PORT="${1:-4173}"
if [ ! -f "$DIR/open-book-builder/index.html" ]; then
  mkdir -p "$DIR/open-book-builder"
  gh release download web-tool-final --repo cwcorella-git/open-book-builder \
    --pattern 'open-book-builder-web-tool-final-site.zip' --dir "$DIR" --clobber
  unzip -qo "$DIR/open-book-builder-web-tool-final-site.zip" -d "$DIR/open-book-builder"
fi
echo "Serving the old web tool at http://localhost:$PORT/open-book-builder/ (Ctrl+C to stop)"
exec python3 -m http.server "$PORT" --bind 127.0.0.1 --directory "$DIR"
