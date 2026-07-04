#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "AI automation environment summary"
echo "PWD: $ROOT"
python --version 2>&1 || true
node --version 2>&1 || true
npm --version 2>&1 || true
bash --version 2>&1 | head -n 1 || true
codex --version 2>&1 || true
agy --version 2>&1 || true
antigravity --version 2>&1 || true
ag --version 2>&1 || true

scripts/agent-loop.sh

echo "Final git status:"
git status --short
echo "Review git diff manually. This script never commits automatically."
