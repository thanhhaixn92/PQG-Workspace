#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

while true; do
  mapfile -t STATE_LINES < <(python - <<'PY'
import json
with open("AI_STATE.json", encoding="utf-8") as f:
    data = json.load(f)
print(data.get("state"))
print(data.get("next_agent"))
print("null" if data.get("lock") is None else data.get("lock"))
print(str(data.get("human_approval_required")).lower())
PY
)
  STATE="${STATE_LINES[0]}"
  NEXT_AGENT="${STATE_LINES[1]}"
  LOCK="${STATE_LINES[2]}"
  HUMAN_APPROVAL="${STATE_LINES[3]}"

  if [[ "$STATE" == "BLOCKED" || "$HUMAN_APPROVAL" == "true" || "$LOCK" != "null" ]]; then
    echo "Stopped: state gate is closed. state=$STATE next_agent=$NEXT_AGENT lock=$LOCK human_approval_required=$HUMAN_APPROVAL"
    exit 0
  fi
  if [[ "$STATE" == "CP5_COMPLETE" && "$NEXT_AGENT" == "human" ]]; then
    echo "Stopped: CP5_COMPLETE is waiting for human approval."
    exit 0
  fi

  BEFORE="$(python - <<'PY'
import json
with open("AI_STATE.json", encoding="utf-8") as f:
    print(json.dumps(json.load(f), sort_keys=True))
PY
)"

  case "$NEXT_AGENT" in
    codex)
      scripts/run-codex.sh
      ;;
    antigravity)
      scripts/run-antigravity.sh
      ;;
    human|done)
      echo "Stopped: next_agent is $NEXT_AGENT."
      exit 0
      ;;
    *)
      echo "Stopped: unknown next_agent $NEXT_AGENT."
      exit 1
      ;;
  esac

  AFTER="$(python - <<'PY'
import json
with open("AI_STATE.json", encoding="utf-8") as f:
    print(json.dumps(json.load(f), sort_keys=True))
PY
)"
  if [[ "$AFTER" == "$BEFORE" ]]; then
    echo "Stopped: agent run made no state change. Manual review required to avoid an infinite loop."
    exit 0
  fi
done
