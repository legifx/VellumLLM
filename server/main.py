"""Entry point: start the local server."""
from __future__ import annotations

import sys

from .app import create_app
from .config import Config


def main() -> int:
    cfg = Config.load()
    try:
        import uvicorn
    except ImportError:
        print("uvicorn is required. Run: pip install -r requirements.txt", file=sys.stderr)
        return 1

    app = create_app(cfg)
    url = f"http://{cfg.host}:{cfg.port}"
    print("=" * 60)
    print("  Local NotebookLM")
    print(f"  UI:        {url}")
    print(f"  CLI bridge: {cfg.cli_adapter}")
    print(f"  Embedder:   {cfg.embedder}   Transcriber: {cfg.transcriber}")
    print(f"  Data dir:   {cfg.data_dir}  (local, gitignored)")
    print("=" * 60)
    if cfg.host not in ("127.0.0.1", "localhost"):
        print(f"  WARNING: binding to {cfg.host} exposes the server beyond localhost.")
    uvicorn.run(app, host=cfg.host, port=cfg.port, log_level="info")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
