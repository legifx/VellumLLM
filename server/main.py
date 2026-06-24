"""Entry point: start the local server."""
from __future__ import annotations

import sys

from . import branding
from .app import create_app
from .config import Config


def render_banner(cfg: Config, color: bool | None = None) -> str:
    use_color = branding.supports_color(color)
    url = f"http://{cfg.host}:{cfg.port}"

    def dim(s: str) -> str:
        return f"\x1b[2m{s}\x1b[0m" if use_color else s

    def bold(s: str) -> str:
        return f"\x1b[1m{s}\x1b[0m" if use_color else s

    lines = ["", branding.hero(color=use_color), "",
             f"  {bold('open')}    {bold(url)}",
             f"  {dim('provider')}  {cfg.cli_adapter}",
             f"  {dim('embedder')}  {cfg.embedder}   {dim('transcriber')} {cfg.transcriber}",
             f"  {dim('data')}      {cfg.data_dir}  {dim('(local)')}"]
    if cfg.host not in ("127.0.0.1", "localhost"):
        warn = f"! binding to {cfg.host} exposes the server beyond localhost"
        lines.append("\n  " + (f"\x1b[33m{warn}\x1b[0m" if use_color else warn))
    lines.append(branding.rule(color=use_color))
    return "\n".join(lines)


def main() -> int:
    cfg = Config.load()
    try:
        import uvicorn
    except ImportError:
        print("uvicorn is required. Run: pip install -r requirements.txt", file=sys.stderr)
        return 1

    app = create_app(cfg)
    print(render_banner(cfg), flush=True)
    uvicorn.run(app, host=cfg.host, port=cfg.port, log_level="warning")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
