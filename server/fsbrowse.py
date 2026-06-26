"""Server-side filesystem browser for the "Add folder" dialog.

The web UI can't read real filesystem paths from the browser, but the server
runs on the same machine as the files — so the picker browses the *server's*
filesystem over a small API and the user adds a folder/file by clicking, never
by typing a path. Files are then ingested in place (no upload, no copy).

Security note: when the server is bound to 0.0.0.0 this exposes the directory
tree to the local network. That trade-off is surfaced in the UI; the default
bind is 127.0.0.1.
"""
from __future__ import annotations

import os
import string
from pathlib import Path

from .ingest import SUPPORTED

# Directories never worth descending into during a recursive search — system /
# vendored / pseudo filesystems that are huge or irrelevant.
_SKIP_SEARCH_DIRS = {
    "node_modules", "__pycache__", ".git", ".venv", "venv", "site-packages",
    "proc", "sys", "dev", "run", "snap", ".cache", "$recycle.bin",
    "windows", "appdata",
}


def _entry(p: Path) -> dict:
    is_dir = p.is_dir()
    return {
        "name": p.name or str(p),
        "path": str(p),
        "is_dir": is_dir,
        "supported": (not is_dir) and p.suffix.lower() in SUPPORTED,
    }


def shortcuts() -> list[dict]:
    """Quick-jump targets: every drive / filesystem root, plus Home and CWD,
    so the whole machine is reachable — not just the user's home folder."""
    out: list[dict] = []
    seen: set[str] = set()

    def add(label: str, path: Path | str) -> None:
        try:
            p = Path(path)
            if not p.exists():
                return
            key = str(p)
            if key not in seen:
                seen.add(key)
                out.append({"label": label, "path": key})
        except OSError:
            return

    if os.name == "nt":
        # Windows: list existing drive letters (C:\, D:\, ...).
        for letter in string.ascii_uppercase:
            add(f"{letter}:", f"{letter}:\\")
    else:
        add("/ (root)", "/")
        # Common mount points for external/extra disks.
        for base in ("/mnt", "/media", "/Volumes"):
            bp = Path(base)
            if bp.is_dir():
                children = [c for c in _safe_iterdir(bp) if c.is_dir()]
                if children:
                    for c in children[:16]:
                        add(c.name, c)
                else:
                    add(base, bp)

    add("Home", Path.home())
    add("Working dir", Path.cwd())
    return out


def _safe_iterdir(p: Path) -> list[Path]:
    try:
        return list(p.iterdir())
    except OSError:
        return []


def list_dir(path: str | None, show_files: bool = True) -> dict:
    """List one directory: subfolders first, then supported files.

    Returns ``{path, parent, entries, shortcuts}``. Raises ValueError for a
    missing/unreadable directory so the caller can return a clean 400.
    """
    target = Path(path).expanduser() if path else Path.home()
    try:
        target = target.resolve()
    except OSError as exc:
        raise ValueError(f"Cannot resolve path: {exc}") from exc
    if not target.exists():
        raise ValueError("That path does not exist.")
    if not target.is_dir():
        raise ValueError("That path is not a folder.")

    dirs: list[dict] = []
    files: list[dict] = []
    try:
        for child in sorted(target.iterdir(), key=lambda c: c.name.lower()):
            if child.name.startswith("."):
                continue  # hide dotfiles/-folders by default
            try:
                if child.is_dir():
                    dirs.append(_entry(child))
                elif show_files and child.suffix.lower() in SUPPORTED:
                    files.append(_entry(child))
            except OSError:
                continue
    except PermissionError as exc:
        raise ValueError("Permission denied for that folder.") from exc

    parent = str(target.parent) if target.parent != target else None
    return {
        "path": str(target),
        "parent": parent,
        "entries": dirs + files,
        "shortcuts": shortcuts(),
    }


def search_dir(path: str | None, query: str, limit: int = 200,
               max_dirs: int = 15000) -> dict:
    """Recursively find folders + supported files under ``path`` whose name
    contains ``query`` (case-insensitive). Bounded for speed: stops after
    ``limit`` hits or scanning ``max_dirs`` directories.

    Returns ``{base, query, results, truncated}``.
    """
    q = (query or "").strip().lower()
    if not q:
        raise ValueError("Type something to search for.")
    base = (Path(path).expanduser() if path else Path.home())
    try:
        base = base.resolve()
    except OSError as exc:
        raise ValueError(f"Cannot resolve path: {exc}") from exc
    if not base.is_dir():
        raise ValueError("That path is not a folder.")

    results: list[dict] = []
    stack: list[Path] = [base]
    scanned = 0
    while stack and len(results) < limit and scanned < max_dirs:
        current = stack.pop()
        scanned += 1
        try:
            entries = list(os.scandir(current))
        except OSError:
            continue
        for e in entries:
            name = e.name
            if name.startswith("."):
                continue
            try:
                is_dir = e.is_dir()
            except OSError:
                continue
            matched = q in name.lower()
            if is_dir:
                if name.lower() not in _SKIP_SEARCH_DIRS:
                    stack.append(Path(e.path))
                if matched:
                    results.append(_entry(Path(e.path)))
            elif matched and Path(name).suffix.lower() in SUPPORTED:
                results.append(_entry(Path(e.path)))
            if len(results) >= limit:
                break

    results.sort(key=lambda r: (not r["is_dir"], r["name"].lower()))
    return {
        "base": str(base),
        "query": query,
        "results": results,
        "truncated": len(results) >= limit or scanned >= max_dirs,
    }
