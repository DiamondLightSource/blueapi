#!/usr/bin/env python3
"""PostToolUse(Edit|Write on *.py): ruff fix + format, matching prek's ruff hooks."""

import json
import subprocess
import sys

path = json.load(sys.stdin)["tool_input"]["file_path"]
# F401 unfixable: Claude often adds an import one edit before the code that uses it.
# Truly unused imports are still caught by prek at commit time.
subprocess.run(
    ["uv", "run", "-q", "ruff", "check", "-q", "--fix", "--unfixable", "F401", path],
    stdout=subprocess.DEVNULL,  # leftover lint findings are prek's job, not hook output
)
subprocess.run(["uv", "run", "-q", "ruff", "format", "-q", path])
