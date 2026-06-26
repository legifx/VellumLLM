"""Entry point: start the local server."""
from __future__ import annotations

import sys

from . import branding
from .app import create_app
from .config import Config


def lan_ip() -> str | None:
    """Best-effort primary LAN IP of this machine (the default-route interface).

    No packets are sent — connecting a UDP socket just selects the local address
    the kernel would use to reach the internet, which is the address other
    devices on the network use to reach us.
    """
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except OSError:
        return None
    finally:
        s.close()


def render_banner(cfg: Config, color: bool | None = None) -> str:
    use_color = branding.supports_color(color)
    # 0.0.0.0/:: means "all interfaces" — not a browsable address. Show the real
    # LAN URL other devices use, plus the local one.
    on_network = cfg.host in ("0.0.0.0", "::", "0")

    def dim(s: str) -> str:
        return f"\x1b[2m{s}\x1b[0m" if use_color else s

    def bold(s: str) -> str:
        return f"\x1b[1m{s}\x1b[0m" if use_color else s

    lines = ["", branding.hero(color=use_color), ""]
    if on_network:
        ip = lan_ip() or cfg.host
        lines.append(f"  {bold('open')}    {bold(f'http://{ip}:{cfg.port}')}  {dim('(network)')}")
        lines.append(f"  {dim('local')}   http://127.0.0.1:{cfg.port}")
    else:
        lines.append(f"  {bold('open')}    {bold(f'http://{cfg.host}:{cfg.port}')}")
    lines += [
        f"  {dim('provider')}  {cfg.cli_adapter}",
        f"  {dim('embedder')}  {cfg.embedder}   {dim('transcriber')} {cfg.transcriber}",
        f"  {dim('data')}      {cfg.data_dir}  {dim('(local)')}",
    ]
    if not on_network and cfg.host not in ("127.0.0.1", "localhost"):
        warn = f"! binding to {cfg.host} exposes the server beyond localhost"
        lines.append("\n  " + (f"\x1b[33m{warn}\x1b[0m" if use_color else warn))
    elif on_network:
        warn = "! reachable by other devices on your network — there is no login"
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
