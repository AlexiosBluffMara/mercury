import os
from unittest.mock import patch

import pytest

from mercury import genai_client


def _clean_env() -> dict[str, str]:
    keys = (
        "GOOGLE_API_KEY",
        "GEMINI_API_KEY",
        "GOOGLE_AI_STUDIO_API_KEY",
        "GOOGLE_GENAI_USE_VERTEXAI",
        "GOOGLE_CLOUD_PROJECT",
        "GOOGLE_CLOUD_LOCATION",
    )
    return {k: v for k, v in os.environ.items() if k not in keys}


def test_detect_mode_no_creds_falls_through_to_vertex():
    with patch.dict(os.environ, _clean_env(), clear=True):
        assert genai_client.detect_mode() == "vertex"


def test_detect_mode_ai_studio_key():
    env = _clean_env()
    env["GEMINI_API_KEY"] = "fake-key"
    with patch.dict(os.environ, env, clear=True):
        assert genai_client.detect_mode() == "ai_studio"


def test_detect_mode_vertex_flag():
    env = _clean_env()
    env["GOOGLE_GENAI_USE_VERTEXAI"] = "true"
    with patch.dict(os.environ, env, clear=True):
        assert genai_client.detect_mode() == "vertex"


def test_detect_mode_vertex_project_implies_vertex():
    env = _clean_env()
    env["GOOGLE_CLOUD_PROJECT"] = "my-project"
    with patch.dict(os.environ, env, clear=True):
        assert genai_client.detect_mode() == "vertex"


def test_make_client_ai_studio_with_key():
    env = _clean_env()
    env["GEMINI_API_KEY"] = "fake-key"
    with patch.dict(os.environ, env, clear=True):
        client = genai_client.make_client("ai_studio")
        assert client is not None


def test_make_client_ai_studio_missing_key_raises():
    with patch.dict(os.environ, _clean_env(), clear=True):
        with pytest.raises(ValueError, match="AI Studio"):
            genai_client.make_client("ai_studio")


def test_make_client_vertex_missing_project_raises():
    with patch.dict(os.environ, _clean_env(), clear=True):
        with pytest.raises(ValueError, match="Vertex"):
            genai_client.make_client("vertex")


def test_make_client_vertex_with_kwargs():
    with patch.dict(os.environ, _clean_env(), clear=True):
        client = genai_client.make_client(
            "vertex",
            project="test-project",
            location="us-central1",
        )
        assert client is not None


def test_make_client_unknown_mode_raises():
    with pytest.raises(ValueError, match="Unknown genai mode"):
        genai_client.make_client("nonsense")  # type: ignore[arg-type]


def test_has_credentials_with_ai_studio_key():
    env = _clean_env()
    env["GOOGLE_API_KEY"] = "fake-key"
    with patch.dict(os.environ, env, clear=True):
        ok, mode = genai_client.has_credentials()
        assert ok is True
        assert mode == "ai_studio"


def test_has_credentials_with_vertex():
    env = _clean_env()
    env["GOOGLE_GENAI_USE_VERTEXAI"] = "true"
    env["GOOGLE_CLOUD_PROJECT"] = "p"
    with patch.dict(os.environ, env, clear=True):
        ok, mode = genai_client.has_credentials()
        assert ok is True
        assert mode == "vertex"


def test_has_credentials_neither():
    with patch.dict(os.environ, _clean_env(), clear=True):
        ok, mode = genai_client.has_credentials()
        assert ok is False
        assert mode is None
