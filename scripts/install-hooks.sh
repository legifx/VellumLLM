#!/usr/bin/env bash
# Install the project git hooks into .git/hooks.
set -euo pipefail
REPO_ROOT="$(git rev-parse --show-toplevel)"
cp "$REPO_ROOT/scripts/pre-commit" "$REPO_ROOT/.git/hooks/pre-commit"
chmod +x "$REPO_ROOT/.git/hooks/pre-commit"
echo "✓ Installed pre-commit hook (secret scan + blocked-path guard)."
