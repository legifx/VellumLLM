from server.config import Config
from server.main import render_banner


def test_localhost_banner_shows_plain_url():
    out = render_banner(Config(host="127.0.0.1", port=8008), color=False)
    assert "http://127.0.0.1:8008" in out
    assert "(network)" not in out
    assert "exposes the server" not in out


def test_network_banner_never_prints_bind_wildcard_as_url():
    out = render_banner(Config(host="0.0.0.0", port=8008), color=False)
    # The open line must be a browsable address, not the 0.0.0.0 wildcard.
    assert "open    http://0.0.0.0:8008" not in out
    assert "(network)" in out
    assert "http://127.0.0.1:8008" in out          # local URL still offered
    assert "no login" in out                        # exposure warning
