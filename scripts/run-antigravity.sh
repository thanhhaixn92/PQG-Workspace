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

find_antigravity_cli() {
  local candidate
  for candidate in agy antigravity ag; do
    if ! command -v "$candidate" >/dev/null 2>&1; then
      continue
    fi
    help_text="$("$candidate" --help 2>&1)"
    if printf '%s\n' "$help_text" | grep -Eq '(^|[[:space:]])-p([[:space:],]|$)|--prompt'; then
      if printf '%s\n' "$help_text" | grep -q -- '--sandbox'; then
        printf '%s\t%s\n' "$candidate" "sandbox"
      else
        printf '%s\t%s\n' "$candidate" "nosandbox"
      fi
      return 0
    fi
    echo "Skipping $candidate: non-interactive -p/--prompt support was not found in --help." >&2
  done
  return 1
}

block_antigravity() {
  local message="$1"
  MESSAGE="$message" python - <<'PY'
import json, os
path = "AI_STATE.json"
with open(path, encoding="utf-8") as f:
    data = json.load(f)
data["state"] = "BLOCKED"
data["next_agent"] = "human"
data["lock"] = None
data["last_agent"] = "automation"
data["last_result"] = os.environ["MESSAGE"]
data["human_approval_required"] = True
data["risk_level"] = "medium"
with open(path, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2)
    f.write("\n")
PY
  echo "Blocked: $message"
}

set_antigravity_lock() {
  python - <<'PY'
import json
path = "AI_STATE.json"
with open(path, encoding="utf-8") as f:
    data = json.load(f)
data["lock"] = "antigravity"
with open(path, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2)
    f.write("\n")
PY
}

release_antigravity_lock() {
  python - <<'PY'
import json
path = "AI_STATE.json"
with open(path, encoding="utf-8") as f:
    data = json.load(f)
if data.get("lock") == "antigravity":
    data["lock"] = None
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
        f.write("\n")
PY
}

CLI_RESULT="$(find_antigravity_cli || true)"
CLI="$(printf '%s' "$CLI_RESULT" | cut -f1)"
CLI_SANDBOX="$(printf '%s' "$CLI_RESULT" | cut -f2)"

if [[ -n "$CLI" ]]; then
  set_antigravity_lock
  trap release_antigravity_lock EXIT
  echo "$CLI CLI detected. Safe prompt:"
  echo "$PROMPT"
  if [[ "$CLI_SANDBOX" == "sandbox" ]]; then
    CLI_ARGS=(--sandbox -p "$PROMPT")
  else
    CLI_ARGS=(-p "$PROMPT")
  fi
  if ! "$CLI" "${CLI_ARGS[@]}"; then
    block_antigravity "$CLI CLI execution failed."
    exit 1
  fi
else
  echo "Antigravity CLI not found."
  echo "GUI fallback:"
  echo "1. Open Antigravity IDE."
  echo "2. Open this repo: $ROOT"
  echo "3. Run /verify-and-handoff."
  block_antigravity "Antigravity CLI unavailable or missing non-interactive -p support. Human must use GUI fallback and explicitly reset AI_STATE.json before resuming automation."
fi
