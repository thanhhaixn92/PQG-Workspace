#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

read_state() {
  python - <<'PY'
import json
with open("AI_STATE.json", encoding="utf-8") as f:
    data = json.load(f)
print(data.get("state"))
print(data.get("next_agent"))
print("null" if data.get("lock") is None else data.get("lock"))
print(str(data.get("human_approval_required")).lower())
PY
}

mapfile -t STATE_LINES < <(read_state)
STATE="${STATE_LINES[0]}"
NEXT_AGENT="${STATE_LINES[1]}"
LOCK="${STATE_LINES[2]}"
HUMAN_APPROVAL="${STATE_LINES[3]}"

if [[ "$STATE" == "CP5_COMPLETE" && "$NEXT_AGENT" == "human" ]]; then
  echo "Stopped: CP5_COMPLETE is waiting for human approval."
  exit 0
fi
if [[ "$STATE" == "BLOCKED" || "$HUMAN_APPROVAL" == "true" || "$LOCK" != "null" ]]; then
  echo "Stopped: state gate is closed. state=$STATE next_agent=$NEXT_AGENT lock=$LOCK human_approval_required=$HUMAN_APPROVAL"
  exit 0
fi
if [[ "$NEXT_AGENT" != "antigravity" ]]; then
  echo "Stopped: next_agent is $NEXT_AGENT, not antigravity."
  exit 0
fi

PROMPT="Read .agents/skills/verify-and-handoff/SKILL.md and run /verify-and-handoff with safe checks only."

if command -v antigravity >/dev/null 2>&1; then
  echo "Antigravity CLI detected. Safe prompt:"
  echo "$PROMPT"
  antigravity "$PROMPT"
elif command -v ag >/dev/null 2>&1; then
  echo "ag CLI detected. Safe prompt:"
  echo "$PROMPT"
  ag "$PROMPT"
else
  echo "Antigravity CLI not found."
  echo "GUI fallback:"
  echo "1. Open Antigravity IDE."
  echo "2. Open this repo: $ROOT"
  echo "3. Run /verify-and-handoff."
fi
