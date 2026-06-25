"""Multiple notebooks ("Vellums"), one folder each.

Every Vellum lives in its own directory under ``<data_dir>/notebooks/<id>/``:

    notebooks/
      <id>/
        meta.json          name, category, timestamps
        notebook.sqlite3    that Vellum's private index (one Store)
        cache/              per-Vellum scratch space

This keeps Vellums fully isolated: deleting one removes a single folder, a CLI
agent can open exactly one, and there is no shared pool to leak across. The
registry is just the filesystem — listing means scanning the folder, so there is
no central index file to drift out of sync.
"""
from __future__ import annotations

import json
import re
import time
from dataclasses import asdict, dataclass
from pathlib import Path

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def slugify(name: str) -> str:
    s = _SLUG_RE.sub("-", name.strip().lower()).strip("-")
    return s or "vellum"


@dataclass
class Notebook:
    id: str
    name: str
    category: str = ""
    created_at: float = 0.0
    updated_at: float = 0.0
    # Populated by the registry when listing; not persisted in meta.json.
    source_count: int = 0

    def to_dict(self) -> dict:
        return asdict(self)


class NotebookRegistry:
    """Filesystem-backed registry of notebooks under ``base``."""

    def __init__(self, base: Path):
        self.base = Path(base)
        self.base.mkdir(parents=True, exist_ok=True)

    # ---- paths -----------------------------------------------------------
    def dir(self, notebook_id: str) -> Path:
        return self.base / notebook_id

    def db_path(self, notebook_id: str) -> Path:
        return self.dir(notebook_id) / "notebook.sqlite3"

    def cache_dir(self, notebook_id: str) -> Path:
        d = self.dir(notebook_id) / "cache"
        d.mkdir(parents=True, exist_ok=True)
        return d

    def _meta_path(self, notebook_id: str) -> Path:
        return self.dir(notebook_id) / "meta.json"

    # ---- read ------------------------------------------------------------
    def exists(self, notebook_id: str) -> bool:
        return self._meta_path(notebook_id).exists()

    def get(self, notebook_id: str) -> Notebook | None:
        mp = self._meta_path(notebook_id)
        if not mp.exists():
            return None
        try:
            data = json.loads(mp.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None
        return Notebook(
            id=data.get("id", notebook_id),
            name=data.get("name", notebook_id),
            category=data.get("category", ""),
            created_at=data.get("created_at", 0.0),
            updated_at=data.get("updated_at", 0.0),
        )

    def list(self) -> list[Notebook]:
        out: list[Notebook] = []
        for child in sorted(self.base.iterdir() if self.base.exists() else []):
            if not child.is_dir():
                continue
            nb = self.get(child.name)
            if nb:
                out.append(nb)
        out.sort(key=lambda n: (n.category.lower(), n.created_at))
        return out

    # ---- write -----------------------------------------------------------
    def _unique_id(self, name: str) -> str:
        base = slugify(name)
        candidate = base
        i = 2
        while (self.base / candidate).exists():
            candidate = f"{base}-{i}"
            i += 1
        return candidate

    def _save(self, nb: Notebook) -> None:
        self.dir(nb.id).mkdir(parents=True, exist_ok=True)
        self._meta_path(nb.id).write_text(
            json.dumps(
                {
                    "id": nb.id, "name": nb.name, "category": nb.category,
                    "created_at": nb.created_at, "updated_at": nb.updated_at,
                },
                indent=2, ensure_ascii=False,
            ),
            encoding="utf-8",
        )

    def create(self, name: str, category: str = "") -> Notebook:
        name = (name or "").strip() or "Untitled Vellum"
        now = time.time()
        nb = Notebook(id=self._unique_id(name), name=name,
                      category=(category or "").strip(),
                      created_at=now, updated_at=now)
        self._save(nb)
        return nb

    def update(self, notebook_id: str, *, name: str | None = None,
               category: str | None = None) -> Notebook | None:
        nb = self.get(notebook_id)
        if nb is None:
            return None
        if name is not None and name.strip():
            nb.name = name.strip()
        if category is not None:
            nb.category = category.strip()
        nb.updated_at = time.time()
        self._save(nb)
        return nb

    def delete(self, notebook_id: str) -> bool:
        d = self.dir(notebook_id)
        if not d.exists() or not self._meta_path(notebook_id).exists():
            return False
        import shutil
        shutil.rmtree(d, ignore_errors=True)
        return True

    # ---- migration -------------------------------------------------------
    def migrate_legacy(self, legacy_db: Path, name: str = "My Vellum") -> Notebook | None:
        """If an old single-pool ``notebook.sqlite3`` exists and no notebooks do
        yet, adopt it as the first Vellum so existing data is not lost."""
        if self.list() or not legacy_db.exists():
            return None
        nb = self.create(name)
        try:
            legacy_db.replace(self.db_path(nb.id))
        except OSError:
            import shutil
            shutil.copy2(legacy_db, self.db_path(nb.id))
        return nb
