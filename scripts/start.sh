#!/usr/bin/env bash
# Local NotebookLM launcher: checks deps, sets up a venv, starts the server.
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

# Pick a Python (3.10+).
PY="${PYTHON:-}"
if [ -z "$PY" ]; then
  for c in python3.12 python3.11 python3.10 python3; do
    command -v "$c" >/dev/null 2>&1 && PY="$c" && break
  done
fi
[ -n "$PY" ] || { echo "Python 3.10+ not found. Install it and retry."; exit 1; }

VENV="$REPO_ROOT/.venv"
if [ ! -d "$VENV" ]; then
  echo "Creating virtualenv (.venv)…"
  "$PY" -m venv "$VENV"
fi
# shellcheck disable=SC1091
source "$VENV/bin/activate"

echo "Installing core dependencies…"
pip install -q --upgrade pip
pip install -q -r requirements.txt

# Install the secret-scan pre-commit hook (no-op if not a git checkout).
if [ -d "$REPO_ROOT/.git" ]; then
  bash "$REPO_ROOT/scripts/install-hooks.sh" || true
fi

if ! command -v ffmpeg >/dev/null 2>&1; then
  echo "Note: ffmpeg not found — audio/video ingestion will be limited."
fi

echo "Starting Local NotebookLM…"
exec python -m server.main
