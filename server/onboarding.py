"""Interactive first-run setup for Vellum (`vellum init`).

Draws the brand mark, asks a short, well-defaulted set of questions, validates
input with friendly re-prompts, and writes a commented .env you can also edit by
hand. Repeatable (`--reconfigure`) and scriptable (`--yes` + flags / env) for CI.
"""
from __future__ import annotations

import argparse
import os
import shutil
import socket
import sys
from pathlib import Path

from . import branding
from .config import PROJECT_ROOT, load_dotenv


def env_path() -> Path:
    return Path(os.environ.get("VELLUM_ENV_FILE", PROJECT_ROOT / ".env"))

ADAPTERS = ["claude-code", "codex", "hermes", "command"]
LANGUAGES = ["en", "de"]
MODALITIES = ["text", "image", "audio", "video"]

# Option descriptions shown in the clickable menus (so every choice is visible).
ADAPTER_OPTS = [
    ("claude-code", "Anthropic Claude Code CLI (`claude`)"),
    ("codex", "OpenAI Codex CLI (`codex`)"),
    ("hermes", "Hermes agent CLI (`hermes`) — OpenRouter / Nous models"),
    ("command", "Any other CLI that reads a prompt on stdin"),
]
LANGUAGE_OPTS = [("en", "English"), ("de", "Deutsch")]
EMBEDDER_OPTS = [
    ("lexical", "instant, no downloads, dependency-free (hashing)"),
    ("semantic", "better recall via sentence-transformers (extra install)"),
]
MODALITY_OPTS = [
    ("text", "documents: pdf, txt, md, docx, pptx, csv, html"),
    ("image", "png, jpg, webp, gif — OCR'd text + filename caption"),
    ("audio", "mp3, wav, m4a, flac — needs whisper + ffmpeg"),
    ("video", "mp4, mov, mkv — keyframes + transcription, needs ffmpeg"),
]
COLOR_OPTS = [("1", "colored terminal banners"), ("0", "plain, no color")]
NETWORK_OPTS = [
    ("127.0.0.1", "Local only — reachable just from this machine (recommended)"),
    ("0.0.0.0", "Whole network — other devices on your LAN can open it"),
]
NETWORK_WARN = {
    "0.0.0.0": "Heads up: 0.0.0.0 exposes the web UI (and the server file browser) "
               "to every device on your network. There is no login. Only use this on "
               "a network you trust.",
}

# Keys this tool manages in .env. Anything else found is preserved verbatim.
MANAGED_KEYS = [
    "MMRAG_CLI_ADAPTER", "MMRAG_CLI_COMMAND", "MMRAG_LANGUAGE", "MMRAG_DATA_DIR",
    "MMRAG_HOST", "MMRAG_PORT", "MMRAG_EMBEDDER", "MMRAG_TRANSCRIBER", "MMRAG_COLOR",
]


# --------------------------------------------------------------------------- #
# styling
# --------------------------------------------------------------------------- #
class Style:
    def __init__(self, color: bool):
        self.color = color

    def _wrap(self, code: str, s: str) -> str:
        return f"\x1b[{code}m{s}\x1b[0m" if self.color else s

    def bold(self, s: str) -> str:
        return self._wrap("1", s)

    def dim(self, s: str) -> str:
        return self._wrap("2", s)

    def accent(self, s: str) -> str:
        return self._wrap("38;5;180", s)

    def ok(self, s: str) -> str:
        return self._wrap("38;5;108", s)

    def warn(self, s: str) -> str:
        return self._wrap("38;5;179", s)


# --------------------------------------------------------------------------- #
# prompting
# --------------------------------------------------------------------------- #
class Prompter:
    def __init__(self, interactive: bool, style: Style):
        self.interactive = interactive
        self.s = style

    def ask(self, label, explain, default, validate=None, choices=None):
        """Return a validated value. validate(raw) -> (ok, parsed_or_message)."""
        if not self.interactive:
            ok, parsed = (True, default) if validate is None else validate(str(default))
            if not ok:
                raise SystemExit(f"Invalid non-interactive value for {label!r}: {parsed}")
            return parsed

        hint = f" {self.s.dim('[' + str(default) + ']')}"
        if choices:
            explain = f"{explain} ({'/'.join(choices)})"
        while True:
            print(f"\n{self.s.bold(label)}")
            print(self.s.dim("  " + explain))
            raw = input(f"  {self.s.accent('>')}{hint} ").strip()
            candidate = raw if raw else str(default)
            if choices and candidate not in choices:
                print(self.s.warn(f"  please choose one of: {', '.join(choices)}"))
                continue
            if validate is None:
                return candidate
            ok, parsed = validate(candidate)
            if not ok:
                print(self.s.warn(f"  {parsed}"))
                continue
            return parsed

    def confirm(self, label, explain, default: bool) -> bool:
        def _v(raw: str):
            t = raw.strip().lower()
            if t in ("y", "yes", "true", "1", "on"):
                return True, True
            if t in ("n", "no", "false", "0", "off"):
                return True, False
            return False, "answer yes or no"
        return self.ask(label, explain, "yes" if default else "no", validate=_v)

    def select(self, label, explain, options, default, warn_on=None):
        """Pick ONE option by clicking a number. ``options`` is a list of
        ``(value, description)``; every choice is shown, so nothing is hidden.

        ``warn_on`` maps a value -> warning string shown after it is chosen.
        Non-interactive: returns ``default`` (must be a valid value)."""
        values = [v for v, _ in options]
        if not self.interactive:
            chosen = default if default in values else values[0]
            self._maybe_warn(chosen, warn_on)
            return chosen
        while True:
            print(f"\n{self.s.bold(label)}")
            print(self.s.dim("  " + explain))
            for i, (val, desc) in enumerate(options, 1):
                mark = self.s.accent("●") if val == default else self.s.dim("○")
                tag = self.s.dim(" (default)") if val == default else ""
                print(f"  {mark} {self.s.bold(str(i))}) {self.s.bold(val)}{tag}")
                print(self.s.dim(f"       {desc}"))
            raw = input(f"  {self.s.accent('>')} {self.s.dim('[' + str(default) + ']')} ").strip()
            if not raw:
                self._maybe_warn(default, warn_on)
                return default
            if raw.isdigit() and 1 <= int(raw) <= len(values):
                chosen = values[int(raw) - 1]
            elif raw in values:
                chosen = raw
            else:
                print(self.s.warn("  pick a number from the list."))
                continue
            self._maybe_warn(chosen, warn_on)
            return chosen

    def _maybe_warn(self, value, warn_on):
        if warn_on and value in warn_on:
            print(self.s.warn(f"  {warn_on[value]}"))

    def multiselect(self, label, explain, options, defaults, forced=()):
        """Pick SEVERAL options by clicking numbers (comma-separated). ``forced``
        values are always included. Returns the chosen values in option order."""
        values = [v for v, _ in options]
        if not self.interactive:
            chosen = [v for v in values if v in defaults or v in forced]
            return chosen or list(forced)
        while True:
            print(f"\n{self.s.bold(label)}")
            print(self.s.dim("  " + explain))
            for i, (val, desc) in enumerate(options, 1):
                on = val in defaults or val in forced
                box = self.s.accent("[x]") if on else self.s.dim("[ ]")
                lock = self.s.dim(" (always on)") if val in forced else ""
                print(f"  {box} {self.s.bold(str(i))}) {self.s.bold(val)}{lock}")
                print(self.s.dim(f"       {desc}"))
            shown = ",".join(str(i) for i, (v, _) in enumerate(options, 1)
                             if v in defaults or v in forced)
            raw = input(f"  {self.s.accent('>')} {self.s.dim('[' + shown + ']')} ").strip()
            picks = [p.strip() for p in raw.replace(" ", ",").split(",") if p.strip()]
            if not picks:
                chosen = [v for v in values if v in defaults or v in forced]
                return chosen or list(forced)
            sel = set(forced)
            bad = False
            for p in picks:
                if p.isdigit() and 1 <= int(p) <= len(values):
                    sel.add(values[int(p) - 1])
                elif p in values:
                    sel.add(p)
                else:
                    bad = True
            if bad:
                print(self.s.warn("  use numbers from the list, comma-separated."))
                continue
            return [v for v in values if v in sel]


# --------------------------------------------------------------------------- #
# validators
# --------------------------------------------------------------------------- #
def _v_port(raw: str):
    try:
        p = int(raw)
    except ValueError:
        return False, "enter a number"
    if not (1024 <= p <= 65535):
        return False, "pick a port between 1024 and 65535"
    return True, p


def _port_is_free(port: int, host: str = "127.0.0.1") -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind((host, port))
            return True
        except OSError:
            return False


def _v_modalities(raw: str):
    parts = [p.strip().lower() for p in raw.replace(" ", ",").split(",") if p.strip()]
    bad = [p for p in parts if p not in MODALITIES]
    if bad:
        return False, f"unknown modality: {', '.join(bad)} (choose from {', '.join(MODALITIES)})"
    chosen = ["text"] + [m for m in MODALITIES if m != "text" and m in parts]
    return True, chosen


# --------------------------------------------------------------------------- #
# .env reading / writing
# --------------------------------------------------------------------------- #
def read_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for line in path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        k, _, v = s.partition("=")
        values[k.strip()] = v.strip().strip('"').strip("'")
    return values


def preserved_lines(path: Path) -> list[str]:
    """Keep any non-managed KEY=VALUE lines a user may have added."""
    if not path.exists():
        return []
    keep = []
    for line in path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        key = s.split("=", 1)[0].strip()
        if key not in MANAGED_KEYS and key.startswith(("MMRAG_", "VELLUM_")):
            keep.append(line.rstrip())
    return keep


def write_env(path: Path, cfg: dict, extra: list[str]) -> None:
    L = []
    add = L.append
    add("# Vellum configuration — written by `vellum init`.")
    add("# Edit by hand any time; re-run `vellum init --reconfigure` to change it here.")
    add("# This file is gitignored and stays on your machine.")
    add("")
    add("# Which local CLI answers chat. One of: claude-code | codex | hermes | command")
    add(f"MMRAG_CLI_ADAPTER={cfg['adapter']}")
    if cfg["adapter"] == "command":
        add("# Command for the generic adapter — reads the prompt on stdin, writes the answer.")
        add(f'MMRAG_CLI_COMMAND={cfg["command"]}')
    add("")
    add("# UI language (en | de).")
    add(f"MMRAG_LANGUAGE={cfg['language']}")
    add("")
    add("# Where your sources, index and cache live (local, gitignored).")
    add(f"MMRAG_DATA_DIR={cfg['data_dir']}")
    add("")
    add("# Network visibility of the web UI:")
    add("#   127.0.0.1 = local only (recommended)   0.0.0.0 = reachable on your LAN.")
    add("# 0.0.0.0 exposes the UI and file browser to other devices — no login.")
    add(f"MMRAG_HOST={cfg.get('host', '127.0.0.1')}")
    add("")
    add("# port for the web UI.")
    add(f"MMRAG_PORT={cfg['port']}")
    add("")
    add("# Embeddings: hashing (lexical, no downloads) | sentence-transformers (semantic).")
    add(f"MMRAG_EMBEDDER={cfg['embedder']}")
    add("")
    add(f"# Modalities enabled: {', '.join(cfg['modalities'])}.")
    add("# Audio/video need transcription: faster-whisper | whisper | disabled (needs ffmpeg).")
    add(f"MMRAG_TRANSCRIBER={cfg['transcriber']}")
    add("")
    add("# Colored terminal output for vellum's own banners (1 | 0). NO_COLOR also disables it.")
    add(f"MMRAG_COLOR={cfg['color']}")
    if extra:
        add("")
        add("# --- your custom settings (preserved) ---")
        L.extend(extra)
    add("")
    path.write_text("\n".join(L), encoding="utf-8")


# --------------------------------------------------------------------------- #
# flow
# --------------------------------------------------------------------------- #
def _default_language() -> str:
    lang = (os.environ.get("LANG") or os.environ.get("LC_ALL") or "").lower()
    return "de" if lang.startswith("de") else "en"


def run(args: argparse.Namespace) -> int:
    color = branding.supports_color(False if args.no_color else None)
    if args.ascii:
        os.environ["MMRAG_ASCII"] = "1"
    style = Style(color)

    env_file = env_path()
    existing = read_env(env_file)
    if env_file.exists() and not args.reconfigure and not args.yes:
        # Already configured and not explicitly re-running: nothing to do.
        print(style.dim(f"{env_file.name} already exists. Use --reconfigure to change it."))
        return 0

    interactive = sys.stdin.isatty() and not args.yes
    p = Prompter(interactive, style)

    print()
    print(branding.hero(color=color, unicode=(False if args.ascii else None)))
    print()
    if interactive:
        print(style.dim("  Let's set up Vellum. Press Enter to accept the default in brackets."))

    def d(key, fallback):  # default = prior .env value, else flag, else fallback
        return existing.get(key, fallback)

    # 1) provider / adapter — clickable list of every option
    adapter = p.select(
        "Model provider", "Which local CLI should answer questions over your sources.",
        ADAPTER_OPTS, args.adapter or d("MMRAG_CLI_ADAPTER", "claude-code"))
    command = args.command or d("MMRAG_CLI_COMMAND", "")
    if adapter == "command":
        def _v_cmd(raw: str):
            return (True, raw) if raw.strip() else (False, "enter a command, e.g. my-llm --stdin")
        command = p.ask("Command", "CLI that reads a prompt on stdin and prints the answer.",
                        command or "my-llm --stdin", validate=_v_cmd)
    else:
        binname = {"claude-code": "claude", "codex": "codex", "hermes": "hermes"}[adapter]
        if interactive and shutil.which(binname) is None:
            print(style.warn(
                f"  note: '{binname}' isn't on PATH yet — install it before chatting."))

    # 2) language
    language = p.select("Language", "Interface language.", LANGUAGE_OPTS,
                        args.lang or d("MMRAG_LANGUAGE", _default_language()))

    # 3) data dir
    data_dir = p.ask("Data folder", "Where your sources, index and cache are stored.",
                     args.data_dir or d("MMRAG_DATA_DIR", "data"))

    # 4) network visibility — local by default, with a clear exposure warning
    host = p.select(
        "Network visibility", "Who can reach the web UI.", NETWORK_OPTS,
        args.host or d("MMRAG_HOST", "127.0.0.1"), warn_on=NETWORK_WARN)

    # 5) port
    def _v_port_warn(raw: str):
        ok, parsed = _v_port(raw)
        if ok and interactive and not _port_is_free(parsed):
            print(style.warn(f"  heads up: port {parsed} looks busy right now."))
        return ok, parsed
    port = p.ask("Port", "port for the web UI.",
                 args.port or int(d("MMRAG_PORT", 8008)), validate=_v_port_warn)

    # 6) modalities — clickable multi-select, text always on
    mod_defaults = (args.modalities.split(",") if args.modalities
                    else (_modalities_from_env(existing) or "text,image").split(","))
    mod_defaults = [m.strip() for m in mod_defaults if m.strip()]
    modalities = p.multiselect("Modalities", "What kinds of files this Vellum ingests.",
                               MODALITY_OPTS, mod_defaults, forced=("text",))
    wants_av = any(m in modalities for m in ("audio", "video"))
    if wants_av:
        transcriber = "faster-whisper"
        if shutil.which("ffmpeg") is None:
            print(style.warn("  audio/video need ffmpeg on PATH and `pip install faster-whisper`."))
    else:
        transcriber = "disabled"

    # 7) embeddings
    emb_prior = d("MMRAG_EMBEDDER", "hashing")
    emb_default = "semantic" if emb_prior == "sentence-transformers" else "lexical"
    emb_choice = p.select("Embeddings", "How sources are indexed for retrieval.",
                          EMBEDDER_OPTS, args.embedder or emb_default)
    embedder = "sentence-transformers" if emb_choice == "semantic" else "hashing"
    if embedder == "sentence-transformers" and interactive:
        print(style.dim("  semantic embeddings: run `pip install -r requirements-optional.txt`."))

    # 8) color
    color_prior = "1" if d("MMRAG_COLOR", "1") not in ("0", "false", "no") else "0"
    color = p.select("Colored output", "Color in vellum's terminal banners.",
                     COLOR_OPTS, color_prior)

    cfg = {
        "adapter": adapter, "command": command, "language": language,
        "data_dir": data_dir, "host": host, "port": port, "modalities": modalities,
        "transcriber": transcriber, "embedder": embedder, "color": color,
    }

    # write
    write_env(env_file, cfg, preserved_lines(env_file))
    try:
        Path(data_dir).expanduser().mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        print(style.warn(f"  couldn't create data folder '{data_dir}': {exc}"))

    _summary(style, cfg, env_file.name)
    return 0


def _modalities_from_env(existing: dict) -> str:
    if existing.get("MMRAG_TRANSCRIBER", "disabled") != "disabled":
        return "text,image,audio,video"
    return ""


def _summary(style: Style, cfg: dict, env_name: str = ".env") -> None:
    print()
    print(style.accent("  Your Vellum"))
    print(branding.rule(width=40))
    rows = [
        ("provider", cfg["adapter"] + (f"  ({cfg['command']})"
                                       if cfg["adapter"] == "command" else "")),
        ("language", cfg["language"]),
        ("data folder", cfg["data_dir"]),
        ("network", cfg.get("host", "127.0.0.1")
            + ("  (local only)" if cfg.get("host", "127.0.0.1") == "127.0.0.1"
               else "  (exposed on LAN)")),
        ("port", str(cfg["port"])),
        ("modalities", ", ".join(cfg["modalities"])),
        ("embeddings", "semantic" if cfg["embedder"] == "sentence-transformers" else "lexical"),
        ("transcription", cfg["transcriber"]),
        ("color", "on" if cfg["color"] == "1" else "off"),
    ]
    for k, v in rows:
        print(f"  {k:<14}{style.bold(v)}")
    print(branding.rule(width=40))
    print(f"\n  saved to {style.dim(env_name)}")
    print(f"\n  {style.ok('Start it now:')}  {style.bold('./vellum start')}\n")


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="vellum init", description="Set up Vellum.")
    ap.add_argument("--reconfigure", action="store_true", help="re-run setup over an existing .env")
    ap.add_argument("-y", "--yes", action="store_true",
                    help="non-interactive: accept defaults/flags")
    ap.add_argument("--no-color", action="store_true", help="disable colored output")
    ap.add_argument("--ascii", action="store_true", help="force the ASCII brand mark")
    ap.add_argument("--adapter", choices=ADAPTERS, help="model provider adapter")
    ap.add_argument("--command", help="command for the 'command' adapter")
    ap.add_argument("--lang", choices=LANGUAGES, help="interface language")
    ap.add_argument("--data-dir", help="data folder")
    ap.add_argument("--host", choices=["127.0.0.1", "0.0.0.0"],
                    help="network visibility: 127.0.0.1 (local) or 0.0.0.0 (LAN)")
    ap.add_argument("--port", type=int, help="web UI port")
    ap.add_argument("--modalities", help="comma list: text,image,audio,video")
    ap.add_argument("--embedder", choices=["lexical", "semantic"], help="embedding quality")
    return ap


def main(argv: list[str] | None = None) -> int:
    load_dotenv()
    args = build_parser().parse_args(argv)
    try:
        return run(args)
    except (KeyboardInterrupt, EOFError):
        print("\nSetup cancelled.")
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
