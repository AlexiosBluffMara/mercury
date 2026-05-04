"""Shared helpers for direct xAI HTTP integrations."""

from __future__ import annotations


def mercury_xai_user_agent() -> str:
    """Return a stable Mercury-specific User-Agent for xAI HTTP calls."""
    try:
        from mercury_cli import __version__
    except Exception:
        __version__ = "unknown"
    return f"Mercury-Agent/{__version__}"
