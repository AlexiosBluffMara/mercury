from unittest.mock import MagicMock, patch

from tools.google_search import google_search_tool


def test_missing_query_returns_error():
    result = google_search_tool({})
    assert result["ok"] is False
    assert result["error"] == "missing_query"


def test_no_credentials_returns_error():
    with patch("mercury.genai_client.has_credentials", return_value=(False, None)):
        result = google_search_tool({"query": "what time is it"})
    assert result["ok"] is False
    assert result["error"] == "no_credentials"


def test_api_error_propagates():
    with patch("mercury.genai_client.has_credentials", return_value=(True, "ai_studio")):
        with patch("mercury.genai_client.make_client", side_effect=RuntimeError("boom")):
            result = google_search_tool({"query": "test"})
    assert result["ok"] is False
    assert result["error"] == "api_error"
    assert "boom" in result["message"]


def test_happy_path_extracts_citations():
    fake_chunk = MagicMock()
    fake_chunk.web.title = "Example article"
    fake_chunk.web.uri = "https://example.com/article"
    fake_meta = MagicMock()
    fake_meta.web_search_queries = ["test query"]
    fake_meta.grounding_chunks = [fake_chunk]
    fake_candidate = MagicMock()
    fake_candidate.grounding_metadata = fake_meta
    fake_response = MagicMock()
    fake_response.text = "The answer is X."
    fake_response.candidates = [fake_candidate]

    fake_client = MagicMock()
    fake_client.models.generate_content.return_value = fake_response

    with patch("mercury.genai_client.has_credentials", return_value=(True, "ai_studio")):
        with patch("mercury.genai_client.make_client", return_value=fake_client):
            result = google_search_tool({"query": "test"})

    assert result["ok"] is True
    assert result["answer"] == "The answer is X."
    assert len(result["citations"]) == 1
    assert result["citations"][0]["uri"] == "https://example.com/article"
    assert result["search_queries"] == ["test query"]


def test_registered_in_web_toolset():
    from tools.registry import discover_builtin_tools, registry
    discover_builtin_tools()
    entry = next(
        (e for e in registry._snapshot_entries() if e.name == "google_search"),
        None,
    )
    assert entry is not None
    assert entry.toolset == "web"
