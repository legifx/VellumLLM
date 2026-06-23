#!/usr/bin/env python3
"""Self-contained secret / PII scanner for Local NotebookLM.

No external dependency (works even when `gitleaks` is not installed). Scans a
set of files for credential-like and PII-like patterns and exits non-zero on
any finding so it can gate commits and pushes.

Usage:
    python scripts/secret_scan.py                # scan git-tracked + staged files
    python scripts/secret_scan.py path1 path2    # scan explicit paths
    python scripts/secret_scan.py --all          # scan the whole working tree
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Files/dirs that are allowed to contain pattern-like strings (docs, the
# scanner itself, examples). They are still scanned for hard secrets below.
ALLOWLIST_NAMES = {".env.example", "config.example.yaml", "secret_scan.py"}

# Binary / vendored / data extensions we skip entirely.
SKIP_SUFFIXES = {
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".pdf", ".mp3", ".wav", ".m4a",
    ".flac", ".mp4", ".mov", ".mkv", ".db", ".sqlite", ".sqlite3", ".npy",
    ".woff", ".woff2", ".ico", ".zip", ".gz", ".lock",
}
SKIP_DIR_PARTS = {
    ".git", "node_modules", "__pycache__", ".venv", "venv", "data", "cache",
    ".cache", "vectorstore", "index", "transcripts", "embeddings", "logs",
    "dist", "build", "models",
}

# (label, compiled regex). Patterns chosen to catch real secrets with low
# false positives. Placeholders like "sk-..." or "<...>" are excluded.
PATTERNS: list[tuple[str, re.Pattern]] = [
    ("OpenAI/Anthropic-style key", re.compile(r"\bsk-[A-Za-z0-9]{16,}\b")),
    ("Anthropic key", re.compile(r"\bsk-ant-[A-Za-z0-9_\-]{20,}\b")),
    ("GitHub PAT", re.compile(r"\bghp_[A-Za-z0-9]{36,}\b")),
    ("GitHub fine-grained PAT", re.compile(r"\bgithub_pat_[A-Za-z0-9_]{50,}\b")),
    ("AWS access key id", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("Google API key", re.compile(r"\bAIza[0-9A-Za-z_\-]{35}\b")),
    ("Slack token", re.compile(r"\bxox[baprs]-[0-9A-Za-z\-]{10,}\b")),
    ("Stripe secret key", re.compile(r"\b[rs]k_(?:live|test)_[0-9A-Za-z]{20,}\b")),
    ("Private key block", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA |PGP )?PRIVATE KEY-----")),
    ("JWT", re.compile(r"\beyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\b")),
    ("Bearer token", re.compile(r"\bBearer\s+[A-Za-z0-9_\-\.=]{20,}")),
    # Generic assignment of a secret-looking value (not a placeholder).
    ("Hardcoded secret assignment", re.compile(
        r"(?i)\b(?:api[_-]?key|secret|password|passwd|token|access[_-]?key)\b"
        r"\s*[:=]\s*['\"][^'\"\s${}<>]{12,}['\"]")),
    # Absolute home paths that would leak a username.
    ("User home path", re.compile(r"(?:/home/(?!server\b)[A-Za-z0-9._-]+|/Users/[A-Za-z0-9._-]+|C:\\\\Users\\\\[A-Za-z0-9._-]+)")),
    # Email addresses (PII) — exclude obviously safe example/noreply ones.
    ("Email address (possible PII)", re.compile(
        r"\b[A-Za-z0-9._%+\-]+@(?!example\.|localhost|users\.noreply\.github\.com)"
        r"[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b")),
]

# Substrings that mark a match as a deliberate placeholder -> ignore.
PLACEHOLDER_MARKERS = ("placeholder", "example", "your-", "your_", "xxxx", "<", "redacted", "dummy")


def tracked_and_staged() -> list[Path]:
    paths: set[str] = set()
    for cmd in (["git", "ls-files"], ["git", "diff", "--cached", "--name-only"]):
        try:
            out = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, check=True).stdout
            paths.update(line for line in out.splitlines() if line.strip())
        except subprocess.CalledProcessError:
            pass
    return [ROOT / p for p in sorted(paths)]


def walk_all() -> list[Path]:
    result = []
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIR_PARTS]
        for f in filenames:
            result.append(Path(dirpath) / f)
    return result


def should_skip(path: Path) -> bool:
    if not path.is_file():
        return True
    if path.suffix.lower() in SKIP_SUFFIXES:
        return True
    if any(part in SKIP_DIR_PARTS for part in path.parts):
        return True
    return False


def scan_line(line: str, name: str) -> list[str]:
    findings = []
    lowered = line.lower()
    for label, pattern in PATTERNS:
        for m in pattern.finditer(line):
            snippet = m.group(0)
            # Allow documented placeholders.
            if any(mark in lowered for mark in PLACEHOLDER_MARKERS):
                continue
            # The example/config files legitimately show key NAMES, not values.
            if name in ALLOWLIST_NAMES and label == "Hardcoded secret assignment":
                continue
            findings.append(f"{label}: {snippet[:60]}")
    return findings


def main(argv: list[str]) -> int:
    if "--all" in argv:
        files = walk_all()
    elif len(argv) > 1:
        files = [Path(a).resolve() for a in argv[1:]]
    else:
        files = tracked_and_staged()

    total = 0
    for path in files:
        if should_skip(path):
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="strict")
        except (UnicodeDecodeError, OSError):
            continue  # binary or unreadable -> skip
        rel = path.relative_to(ROOT) if str(path).startswith(str(ROOT)) else path
        for i, line in enumerate(text.splitlines(), 1):
            for finding in scan_line(line, path.name):
                print(f"  [!] {rel}:{i}  {finding}")
                total += 1

    if total:
        print(f"\n✗ Secret scan FAILED: {total} potential issue(s) found. Do NOT commit/push.")
        return 1
    print("✓ Secret scan passed: no secrets or PII patterns detected.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
