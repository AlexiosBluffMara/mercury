"""
Mercury CLI - Unified command-line interface for Mercury Agent.

Provides subcommands for:
- mercury chat          - Interactive chat (same as ./mercury)
- mercury gateway       - Run gateway in foreground
- mercury gateway start - Start gateway service
- mercury gateway stop  - Stop gateway service  
- mercury setup         - Interactive setup wizard
- mercury status        - Show status of all components
- mercury cron          - Manage cron jobs
"""

__version__ = "0.11.0"
__release_date__ = "2026.4.23"


# Force UTF-8 stdout/stderr on Windows for ANY mercury_cli import — covers
# direct submodule imports (e.g. copilot_auth) that bypass main.py's setup.
import sys as _sys
if _sys.platform == "win32":
    for _stream in (_sys.stdout, _sys.stderr):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
        except (AttributeError, ValueError):
            pass
del _sys
