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

from pathlib import Path

from .ingest import SUPPORTED


def _entry(p: Path) -> dict:
    is_dir = p.is_dir()
    return {
        "name": p.name or str(p),
        "path": str(p),
        "is_dir": is_dir,
        "supported": (not is_dir) and p.suffix.lower() in SUPPORTED,
    }


def shortcuts() -> list[dict]:
    """Handy starting points for the picker."""
    out = []
    for label, path in (("Home", Path.home()), ("Working dir", Path.cwd())):
        try:
            if path.exists():
                out.append({"label": label, "path": str(path.resolve())})
        except OSError:
            continue
    return out


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
