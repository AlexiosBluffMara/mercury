from unittest.mock import patch

from mercury import tailscale


def test_extract_identity_missing_login_returns_none():
    assert tailscale.extract_identity({}) is None


def test_extract_identity_with_full_headers():
    ident = tailscale.extract_identity({
        "Tailscale-User-Login": "alice@example.com",
        "Tailscale-User-Name": "Alice",
        "Tailscale-User-Profile-Pic": "https://x/y.png",
    })
    assert ident is not None
    assert ident.login == "alice@example.com"
    assert ident.name == "Alice"
    assert ident.profile_picture == "https://x/y.png"


def test_extract_identity_falls_back_to_login_for_name():
    ident = tailscale.extract_identity({"Tailscale-User-Login": "bob@example.com"})
    assert ident.name == "bob@example.com"


def test_extract_identity_case_insensitive():
    ident = tailscale.extract_identity({"tailscale-user-login": "case@x.com"})
    assert ident is not None
    assert ident.login == "case@x.com"


def test_helpers_degrade_when_tailscale_missing():
    with patch("mercury.tailscale.is_installed", return_value=False):
        assert tailscale.status() is None
        assert tailscale.is_running() is False
        assert tailscale.hostname() is None
        assert tailscale.tailnet_ip() is None
        assert tailscale.webui_url() is None
