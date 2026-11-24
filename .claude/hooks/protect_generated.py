#!/usr/bin/env python3
"""PreToolUse(Edit|Write): deny hand-edits to files generated from code."""

import json
import sys

REGENERATE = {
    "docs/reference/openapi.yaml": "uv run blueapi schema -u",
    "helm/blueapi/config_schema.json": "uv run blueapi config-schema -u",
    "helm/blueapi/values.schema.json": "uv run prek run helm-schema --all-files",
    "helm/blueapi/README.md": (
        "edit helm/blueapi/README.md.gotmpl or values.yaml comments, then "
        "uv run prek run helm-docs-built --all-files"
    ),
    "uv.lock": "uv add / uv remove / uv lock",
    "src/blueapi/_version.py": "nothing: setuptools_scm writes it on install",
}

path = json.load(sys.stdin)["tool_input"].get("file_path", "")
for suffix, how in REGENERATE.items():
    if path.endswith("/" + suffix):
        reason = f"{suffix} is generated, don't edit it by hand. Regenerate: {how}"
        print(
            json.dumps(
                {
                    "hookSpecificOutput": {
                        "hookEventName": "PreToolUse",
                        "permissionDecision": "deny",
                        "permissionDecisionReason": reason,
                    }
                }
            )
        )
        break
