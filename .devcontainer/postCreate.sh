#!/usr/bin/env bash
# Runs as root outside the agent sandbox: review changes before rebuilding.
set -euo pipefail

# Recreate the venv then make prek first run faster
uv venv --clear && uv sync && prek install --install-hooks

# Sandboxed Claude Code / Codex / Pi. Pinned so upgrades are reviewed here.
uvx claude-sandbox==5.2.2 install

# Playwright + Chromium for the browser-testing skill (browsers cached in /cache).
# The resolute nodejs package ships without npm.
command -v npm >/dev/null || { apt-get update -y && apt-get install -y --no-install-recommends npm; }
sh /usr/libexec/claude-sandbox/skills/browser-testing/scripts/install-browser-deps.sh
