"""CLI bridge package."""
from .adapters import available_adapters, build_adapter
from .base import CLIAdapter, CLIError

__all__ = ["build_adapter", "available_adapters", "CLIAdapter", "CLIError"]
