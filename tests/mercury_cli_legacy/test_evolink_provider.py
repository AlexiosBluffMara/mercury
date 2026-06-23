"""Tests for EvoLink OpenAI-compatible provider integration."""

from mercury_cli.auth import (
    PROVIDER_REGISTRY,
    resolve_api_key_provider_credentials,
    resolve_provider,
)


def test_evolink_registered():
    pconfig = PROVIDER_REGISTRY["evolink"]
    assert pconfig.name == "EvoLink"
    assert pconfig.auth_type == "api_key"
    assert pconfig.inference_base_url == "https://direct.evolink.ai/v1"
    assert pconfig.api_key_env_vars == ("EVOLINK_API_KEY",)
    assert pconfig.base_url_env_var == "EVOLINK_BASE_URL"


def test_evolink_aliases_resolve():
    assert resolve_provider("evolink") == "evolink"
    assert resolve_provider("evo-link") == "evolink"
    assert resolve_provider("evo_link") == "evolink"


def test_resolve_evolink_credentials(monkeypatch):
    monkeypatch.delenv("EVOLINK_BASE_URL", raising=False)
    monkeypatch.setenv("EVOLINK_API_KEY", "evolink-secret-key")
    creds = resolve_api_key_provider_credentials("evolink")
    assert creds["provider"] == "evolink"
    assert creds["api_key"] == "evolink-secret-key"
    assert creds["base_url"] == "https://direct.evolink.ai/v1"


def test_resolve_evolink_custom_base_url(monkeypatch):
    monkeypatch.setenv("EVOLINK_API_KEY", "evolink-secret-key")
    monkeypatch.setenv("EVOLINK_BASE_URL", "https://gateway.example.com/v1")
    creds = resolve_api_key_provider_credentials("evolink")
    assert creds["base_url"] == "https://gateway.example.com/v1"


def test_runtime_evolink(monkeypatch):
    monkeypatch.delenv("EVOLINK_BASE_URL", raising=False)
    monkeypatch.setenv("EVOLINK_API_KEY", "evolink-key")
    from mercury_cli.runtime_provider import resolve_runtime_provider

    result = resolve_runtime_provider(requested="evolink")
    assert result["provider"] == "evolink"
    assert result["api_mode"] == "chat_completions"
    assert result["api_key"] == "evolink-key"
    assert result["base_url"] == "https://direct.evolink.ai/v1"


def test_evolink_model_and_aux_catalog():
    from agent.auxiliary_client import _API_KEY_PROVIDER_AUX_MODELS
    from mercury_cli.models import _PROVIDER_LABELS, _PROVIDER_MODELS

    assert _PROVIDER_LABELS["evolink"] == "EvoLink"
    assert _PROVIDER_MODELS["evolink"]
    assert _API_KEY_PROVIDER_AUX_MODELS["evolink"]
