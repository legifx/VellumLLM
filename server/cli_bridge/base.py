"""CLI adapter interface and a shared subprocess runner.

An adapter receives a fully-built prompt (system + sources + question) and
returns the model's answer by invoking a *locally installed* CLI. The prompt is
passed on stdin (no shell interpolation, no arg-length limits, no secrets on the
command line). Output is streamed back chunk by chunk.
"""
from __future__ import annotations

import subprocess
from abc import ABC, abstractmethod
from typing import Iterator


class CLIError(RuntimeError):
    pass


class CLIAdapter(ABC):
    name: str = "base"

    @abstractmethod
    def command(self) -> list[str]:
        """The argv to execute. The prompt is fed on stdin."""

    def available(self) -> bool:
        import shutil
        argv = self.command()
        return bool(argv) and shutil.which(argv[0]) is not None

    def stream(self, prompt: str, timeout: int = 120) -> Iterator[str]:
        argv = self.command()
        if not argv:
            raise CLIError(f"Adapter '{self.name}' has no command configured.")
        try:
            proc = subprocess.Popen(
                argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, text=True, bufsize=1,
            )
        except FileNotFoundError as exc:
            raise CLIError(
                f"Could not run '{argv[0]}' for adapter '{self.name}'. Is the CLI "
                f"installed and on PATH? Configure it via MMRAG_CLI_ADAPTER / "
                f"MMRAG_CLI_COMMAND."
            ) from exc

        assert proc.stdin and proc.stdout
        proc.stdin.write(prompt)
        proc.stdin.close()
        try:
            for line in proc.stdout:
                yield line
            proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired as exc:
            proc.kill()
            raise CLIError(f"CLI '{self.name}' timed out after {timeout}s.") from exc
        if proc.returncode not in (0, None):
            err = (proc.stderr.read() if proc.stderr else "").strip()
            raise CLIError(f"CLI '{self.name}' exited with {proc.returncode}: {err[:500]}")

    def complete(self, prompt: str, timeout: int = 120) -> str:
        return "".join(self.stream(prompt, timeout=timeout))
