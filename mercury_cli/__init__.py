"""
Hermes CLI - Unified command-line interface for Hermes Agent.

Provides subcommands for:
- hermes chat          - Interactive chat (same as ./hermes)
- hermes gateway       - Run gateway in foreground
- hermes gateway start - Start gateway service
- hermes gateway stop  - Stop gateway service  
- hermes setup         - Interactive setup wizard
- hermes status        - Show status of all components
- hermes cron          - Manage cron jobs
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
