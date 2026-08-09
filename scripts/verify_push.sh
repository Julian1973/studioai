#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUNTIME_MODULES="${CODEX_NODE_MODULES:-$HOME/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules}"

cd "$ROOT"
echo "Studio push gate: Seven UX Laws + Golden Path"
PYTHONPATH=engine pytest -q cb-studio/test_local_auth.py cb-studio/test_director_ui.py
NODE_PATH="$RUNTIME_MODULES${NODE_PATH:+:$NODE_PATH}" node cb-studio/golden_path_browser.mjs
