#!/usr/bin/env bash
# Thin wrapper kept for compatibility — delegates to the `vellum` launcher.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
exec "$ROOT/vellum" start
