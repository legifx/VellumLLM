#!/usr/bin/env python3
"""Cross-platform launcher for Vellum — the single source of truth.

The OS shims (`vellum` on macOS/Linux, `vellum.cmd` on Windows) just find a
Python interpreter and hand control to this file, so the same behaviour runs
everywhere — including PowerShell and cmd.exe, where a bare bash script can't.

    vellum                 first run sets up, then starts; afterwards just starts
    vellum init [args]     (re)run the guided setup (--reconfigure, --yes, ...)
    vellum start           start the local server
    vellum notebooks       list your Vellums and their ids
    vellum ask -n <id> "question"   answer from one Vellum (CLI)
    vellum update          fetch and install the latest version (git)
    vellum doctor          check prerequisites
    vellum --help

On an interactive start Vellum briefly checks for a newer version and asks
whether to install it. Set VELLUM_NO_UPDATE_CHECK=1 to skip that check.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VENV = ROOT / ".venv"
IS_WINDOWS = os.name == "nt"
REMOTE = os.environ.get("VELLUM_REMOTE", "origin")

HELP = __doc__.split("\n\n", 1)[1].rstrip()


def venv_python() -> Path:
    """Path to the interpreter inside the project virtualenv."""
    return VENV / ("Scripts/python.exe" if IS_WINDOWS else "bin/python")


def require_python() -> None:
    # Runtime guard: the bootstrap interpreter (whatever launched this file) may
    # be older than the project's own minimum.
    if sys.version_info[:2] < (3, 10):  # noqa: UP036
        sys.exit("Vellum needs Python 3.10 or newer. Install it and try again.")


# --- venv + core deps for running the server -----------------------------
def ensure_runtime() -> Path:
    """Make sure the project venv exists with core deps; return its python."""
    require_python()
    py = venv_python()
    if not py.exists():
        print("Creating virtualenv (.venv)…")
        subprocess.check_call([sys.executable, "-m", "venv", str(VENV)])
    if subprocess.call([str(py), "-c", "import fastapi, uvicorn"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) != 0:
        print("Installing core dependencies…")
        subprocess.check_call([str(py), "-m", "pip", "install", "-q", "--upgrade", "pip"])
        subprocess.check_call([str(py), "-m", "pip", "install", "-q", "-r",
                               str(ROOT / "requirements.txt")])
    # Best-effort dev git hook (bash only; harmless to skip on Windows).
    hook = ROOT / "scripts" / "install-hooks.sh"
    if (ROOT / ".git").exists() and hook.exists() and shutil.which("bash"):
        subprocess.call(["bash", str(hook)], stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL)
    return py


def env_file() -> Path:
    return Path(os.environ.get("VELLUM_ENV_FILE", str(ROOT / ".env")))


# --- self-update (git) ----------------------------------------------------
def is_git() -> bool:
    return (ROOT / ".git").exists() and shutil.which("git") is not None


def _git(*args: str, timeout: int | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True,
                          text=True, timeout=timeout)


def current_branch() -> str:
    return _git("rev-parse", "--abbrev-ref", "HEAD").stdout.strip()


def git_fetch() -> bool:
    """Fetch from the remote; never hang the start (10s cap)."""
    try:
        return _git("fetch", "--quiet", REMOTE, timeout=10).returncode == 0
    except (subprocess.TimeoutExpired, OSError):
        return False


def commits_behind() -> int:
    """How many commits upstream is ahead. 0 if up to date / no upstream."""
    if _git("rev-parse", "@{u}").returncode != 0:
        return 0
    out = _git("rev-list", "--count", "HEAD..@{u}").stdout.strip()
    return int(out) if out.isdigit() else 0


def do_update() -> bool:
    branch = current_branch()
    print(f"Updating Vellum ({branch})…")
    pull = _git("pull", "--ff-only", REMOTE, branch)
    sys.stdout.write(pull.stdout)
    if pull.returncode != 0:
        sys.stderr.write(pull.stderr)
        print("Automatic update failed — you may have local changes.\n"
              "Resolve them with git (e.g. 'git stash') and run 'vellum update' again.",
              file=sys.stderr)
        return False
    ensure_runtime()  # reinstall in case requirements changed
    print("Vellum is up to date.")
    return True


def cmd_update() -> int:
    if not is_git():
        print("This Vellum isn't a git checkout, so it can't self-update.\n"
              "Reinstall the latest version from https://github.com/legifx/VellumLLM",
              file=sys.stderr)
        return 1
    print("Checking for updates…")
    if not git_fetch():
        print("Couldn't reach the remote (offline?). Try again later.", file=sys.stderr)
        return 1
    if commits_behind() > 0:
        return 0 if do_update() else 1
    print("Already on the latest version.")
    return 0


def maybe_offer_update() -> None:
    """Offer an update at the start of an interactive session (Yes/No)."""
    if os.environ.get("VELLUM_NO_UPDATE_CHECK") == "1" or not is_git():
        return
    if not sys.stdin.isatty():
        return
    if not git_fetch():
        return
    behind = commits_behind()
    if behind <= 0:
        return
    print(f"\n  ↑ A new Vellum version is available ({behind} commit(s) behind).")
    try:
        ans = input("  Install it now? [y/N] ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        return
    if ans in ("y", "yes", "j", "ja"):
        if do_update():
            # Re-exec the freshly updated launcher; skip the re-check.
            env = {**os.environ, "VELLUM_NO_UPDATE_CHECK": "1"}
            raise SystemExit(subprocess.call([sys.executable, str(ROOT / "vellum.py"),
                                              "start"], cwd=str(ROOT), env=env))
        print("  Continuing with the current version.")
    else:
        print("  Skipped. Run 'vellum update' whenever you like.")


# --- commands -------------------------------------------------------------
def cmd_init(args: list[str]) -> int:
    require_python()
    rc = subprocess.call([sys.executable, "-m", "server.onboarding", *args], cwd=str(ROOT))
    # If a venv already exists, check the freshly chosen config's extras now so
    # the user can install them right after setup, not on first ingestion error.
    if rc == 0 and venv_python().exists():
        ensure_optional_deps(venv_python())
    return rc


def cmd_start() -> int:
    maybe_offer_update()
    py = ensure_runtime()
    ensure_optional_deps(py)
    return subprocess.call([str(py), "-m", "server.main"], cwd=str(ROOT))


def cmd_cli(args: list[str]) -> int:
    py = ensure_runtime()
    return subprocess.call([str(py), "-m", "server.cli", *args], cwd=str(ROOT))


# --- optional feature dependencies ----------------------------------------
def ensure_optional_deps(py: Path) -> None:
    """Check that the extras the active config needs are installed; offer to
    pip-install any that are missing. Keeps audio/video & semantic embeddings
    from failing later with 'X is not installed'."""
    probe = subprocess.run([str(py), "-m", "server.deps"], cwd=str(ROOT),
                           capture_output=True, text=True)
    try:
        rep = json.loads(probe.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        return  # never block startup on a probe failure
    if rep.get("ok"):
        return

    missing = rep.get("missing_pip") or []
    if missing:
        print("\n  Some enabled features need extra packages that aren't installed yet:")
        for pkg in missing:
            print(f"    - {pkg}")
        if sys.stdin.isatty():
            try:
                ans = input("  Install them now with pip? [Y/n] ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                ans = "n"
            if ans in ("", "y", "yes", "j", "ja"):
                rc = subprocess.call([str(py), "-m", "pip", "install", *missing])
                if rc == 0:
                    print("  Installed.")
                else:
                    print("  Install failed — run it manually:")
                    print("    pip install " + " ".join(missing))
            else:
                print("  Skipped — those features will error until installed.")
        else:
            print("  Install with:  pip install " + " ".join(missing))

    if rep.get("ffmpeg_missing"):
        print("\n  ! ffmpeg is required for audio/video but was not found on PATH.")
        print("    Linux:  sudo apt install ffmpeg")
        print("    macOS:  brew install ffmpeg")
        print("    Windows: https://ffmpeg.org/download.html  (then add it to PATH)")


def cmd_doctor() -> int:
    require_python()
    print(f"Python:  {sys.version.split()[0]}  ({sys.executable})")
    ffmpeg = "found  (audio/video ready)" if shutil.which("ffmpeg") \
        else "not found  (only needed for audio/video)"
    print(f"ffmpeg:  {ffmpeg}")
    cfg = ".env present" if env_file().exists() else "not set up yet — run vellum init"
    print(f"Config:  {cfg}")
    return 0


def main(argv: list[str]) -> int:
    cmd = argv[0] if argv else ""
    rest = argv[1:]
    if cmd == "init":
        return cmd_init(rest)
    if cmd == "start":
        return cmd_start()
    if cmd == "ask":
        return cmd_cli(["ask", *rest])
    if cmd in ("notebooks", "nb"):
        return cmd_cli(["notebooks", *rest])
    if cmd == "update":
        return cmd_update()
    if cmd == "doctor":
        return cmd_doctor()
    if cmd in ("-h", "--help", "help"):
        print(HELP)
        return 0
    if cmd == "":
        if not env_file().exists():
            cmd_init([])
        return cmd_start()
    print(f"Unknown command: {cmd}", file=sys.stderr)
    print(HELP)
    return 2


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv[1:]))
    except KeyboardInterrupt:
        raise SystemExit(130) from None
