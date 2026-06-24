from server import branding


def test_supports_color_respects_no_color(monkeypatch):
    monkeypatch.setenv("NO_COLOR", "1")
    assert branding.supports_color() is False
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.setenv("MMRAG_COLOR", "0")
    assert branding.supports_color() is False


def test_supports_color_force_overrides(monkeypatch):
    monkeypatch.setenv("NO_COLOR", "1")
    assert branding.supports_color(True) is True


def test_hero_unicode_vs_ascii():
    uni = branding.hero(color=False, unicode=True)
    asc = branding.hero(color=False, unicode=False)
    assert "┏" in uni and "V E L L U M" in uni
    assert "+----------+" in asc and "V E L L U M" in asc
    assert "┏" not in asc


def test_hero_no_color_has_no_escapes():
    out = branding.hero(color=False, unicode=True)
    assert "\x1b[" not in out


def test_hero_color_has_escapes():
    out = branding.hero(color=True, unicode=True)
    assert "\x1b[" in out
