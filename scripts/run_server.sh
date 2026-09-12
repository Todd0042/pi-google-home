#!/usr/bin/env bash
set -euo pipefail

# Pi Google Home — Host PC Server Runner
# Starts the FastAPI/WebSocket heavy-lifting server with GPU acceleration

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$ROOT_DIR"

if [ ! -d ".venv-server" ]; then
    echo "[ERROR] .venv-server directory not found. Please create it first." >&2
    exit 1
fi

NV_DIR="$ROOT_DIR/.venv-server/lib/python3.14/site-packages/nvidia"
if [ -d "$NV_DIR" ]; then
    export LD_LIBRARY_PATH="$NV_DIR/cublas/lib:$NV_DIR/cudnn/lib:${LD_LIBRARY_PATH:-}"
fi

echo "==> Starting Pi Google Home Gateway Server on Host PC..."
exec .venv-server/bin/python -m server.api.gateway
