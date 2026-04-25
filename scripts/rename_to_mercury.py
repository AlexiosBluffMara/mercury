"""One-shot rename pass: hermes_{cli,constants,state,logging,time} -> mercury_*.

Run once after `git mv mercury_cli mercury_cli` etc.  Walks all .py files
(excluding .venv, __pycache__, .git, node_modules) and rewrites:

  - `from hermes_X import ...`   ->  `from mercury_X import ...`
  - `import hermes_X`             ->  `import mercury_X`
  - `hermes_X.foo`                ->  `mercury_X.foo`
  - `~/.mercury/`                  ->  `~/.mercury/`

Word-boundary regex prevents collateral matches inside larger
identifiers.  Idempotent — re-runs are no-ops once everything's
renamed.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

MODULES = ["mercury_cli", "mercury_constants", "mercury_state", "mercury_logging", "mercury_time"]
EXCLUDE_DIRS = {".venv", "__pycache__", ".git", "node_modules", ".pytest_cache", ".ruff_cache", "dist", "build"}


def make_patterns() -> list[tuple[re.Pattern, str]]:
    patterns = []
    for old in MODULES:
        new = "mercury_" + old.removeprefix("hermes_")
        patterns.append((re.compile(rf"\b{old}\b"), new))
    patterns.append((re.compile(r"~/\.hermes/"), "~/.mercury/"))
    patterns.append((re.compile(r"~/\.hermes(?=[\b\\\"\'])"), "~/.mercury"))
    return patterns


def rewrite_file(path: Path, patterns: list[tuple[re.Pattern, str]]) -> int:
    try:
        text = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return 0
    new_text = text
    changes = 0
    for pat, repl in patterns:
        new_text, n = pat.subn(repl, new_text)
        changes += n
    if changes and new_text != text:
        path.write_text(new_text, encoding="utf-8")
        return changes
    return 0


def walk(root: Path, suffixes: tuple[str, ...]) -> list[Path]:
    out: list[Path] = []
    stack = [root]
    while stack:
        d = stack.pop()
        try:
            for entry in d.iterdir():
                if entry.is_dir():
                    if entry.name not in EXCLUDE_DIRS:
                        stack.append(entry)
                elif entry.suffix in suffixes:
                    out.append(entry)
        except OSError:
            continue
    return out


def main() -> int:
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.cwd()
    patterns = make_patterns()
    total_files = 0
    total_changes = 0

    py_files = walk(root, (".py", ".pyi", ".toml", ".md", ".cfg", ".ini", ".txt", ".yaml", ".yml"))
    for f in py_files:
        n = rewrite_file(f, patterns)
        if n:
            total_files += 1
            total_changes += n

    print(f"rewrote {total_files} files / {total_changes} replacements")
    return 0


if __name__ == "__main__":
    sys.exit(main())
