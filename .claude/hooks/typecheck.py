#!/usr/bin/env python3
"""Stop: run pyright on src/ and tests/ files Claude edited this session.

Mirrors `tox -e type-checking`. Only Claude's own Edit/Write targets are checked, so
the user's work-in-progress files never hold Claude hostage.
"""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

MAX_RETRIES = 3  # under Claude Code's cap of 8 consecutive stop-hook continuations

hook = json.load(sys.stdin)
root = Path(os.environ.get("CLAUDE_PROJECT_DIR", ".")).resolve()
counter = Path(tempfile.gettempdir()) / f"claude-typecheck-{hook['session_id']}"


def edited_files() -> set[str]:
    files = set()
    for line in Path(hook["transcript_path"]).read_text().splitlines():
        try:
            content = json.loads(line)["message"]["content"]
        except (ValueError, KeyError, TypeError):
            continue
        for block in content if isinstance(content, list) else []:
            if block.get("type") == "tool_use" and block.get("name") in (
                "Edit",
                "Write",
            ):
                files.add(block.get("input", {}).get("file_path", ""))
    return files


files = []
for f in edited_files():
    p = Path(f)
    if p.suffix == ".py" and p.is_file() and p.is_relative_to(root):
        rel = p.relative_to(root)
        if rel.parts[0] in ("src", "tests"):
            files.append(str(rel))
if not files:
    sys.exit(0)

result = subprocess.run(
    ["uv", "run", "--quiet", "pyright", *sorted(files)],
    cwd=root,
    capture_output=True,
    text=True,
)
retries = (
    int(counter.read_text()) if hook.get("stop_hook_active") and counter.exists() else 0
)
if result.returncode == 0 or retries >= MAX_RETRIES:
    counter.unlink(missing_ok=True)
    sys.exit(0)

counter.write_text(str(retries + 1))
# Hook output is capped at 10k chars; pyright's summary is at the end, so keep the tail.
report = (result.stdout + result.stderr)[-9000:]
print(json.dumps({"decision": "block", "reason": f"pyright found errors:\n{report}"}))
