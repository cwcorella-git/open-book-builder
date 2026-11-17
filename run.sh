#!/usr/bin/env bash
# Start Open Book Builder from this checkout (creates the venv on first run).
set -euo pipefail
cd "$(dirname "$(readlink -f "$0")")"
[ -d .venv ] || { uv venv -q .venv && uv pip install -q -e . ; }
exec .venv/bin/open-book-builder "$@"
