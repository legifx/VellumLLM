import pytest

from server.cli_bridge import CLIError, available_adapters, build_adapter
from server.cli_bridge.adapters import CommandAdapter
from server.config import Config


def test_registry_lists_all():
    assert set(available_adapters()) == {"claude-code", "hermes", "codex", "command"}


def test_factory_unknown_adapter_raises():
    with pytest.raises(CLIError):
        build_adapter(Config(cli_adapter="does-not-exist"))


def test_command_adapter_requires_command():
    with pytest.raises(CLIError):
        build_adapter(Config(cli_adapter="command", cli_command=""))


def test_command_adapter_streams_stdin_to_stdout(fake_cli):
    cfg = Config(cli_adapter="command", cli_command=fake_cli)
    adapter = build_adapter(cfg)
    assert isinstance(adapter, CommandAdapter)
    out = adapter.complete("PROMPT WITH SOURCES", timeout=30)
    assert "ANSWER based on sources [S1]" in out


def test_named_adapters_build():
    for name in ("claude-code", "hermes", "codex"):
        adapter = build_adapter(Config(cli_adapter=name))
        assert adapter.command()[0]  # has an executable name
