#!/bin/sh
set -eu
STUDIO_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
python3 -m venv "$STUDIO_ROOT/.venv-mcp"
"$STUDIO_ROOT/.venv-mcp/bin/python" -m pip install -r "$STUDIO_ROOT/requirements-mcp.txt"
printf '%s\n' 'MCP runtime installed. Open Studio → Projects → Agent access for the local client configuration.'
