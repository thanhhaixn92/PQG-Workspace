#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

state_value() {
  python - "$1" <<'PY'
import json, sys
key = sys.argv[1]
with open("AI_STATE.json", encoding="utf-8") as f:
    data = json.load(f)
value = data.get(key)
if value is None:
    print("null")
elif isinstance(value, bool):
    print(str(value).lower())
else:
    print(value)
PY
}

STATE="$(state_value state)"
NEXT_AGENT="$(state_value next_agent)"
LOCK="$(state_value lock)"
HUMAN_APPROVAL="$(state_value human_approval_required)"

if [[ "$STATE" == "CP5_COMPLETE" && "$NEXT_AGENT" == "human" ]]; then
  echo "Stopped: CP5_COMPLETE is waiting for human approval."
  exit 0
fi
if [[ "$STATE" == "BLOCKED" || "$HUMAN_APPROVAL" == "true" || "$LOCK" != "null" ]]; then
  echo "Stopped: state gate is closed. state=$STATE next_agent=$NEXT_AGENT lock=$LOCK human_approval_required=$HUMAN_APPROVAL"
  exit 0
fi
if [[ "$NEXT_AGENT" != "codex" ]]; then
  echo "Stopped: next_agent is $NEXT_AGENT, not codex."
  exit 0
fi

python - <<'PY'
import json
path = "AI_STATE.json"
with open(path, encoding="utf-8") as f:
    data = json.load(f)
data["lock"] = "codex"
with open(path, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2)
    f.write("\n")
PY

cleanup() {
  python - <<'PY'
import json
path = "AI_STATE.json"
with open(path, encoding="utf-8") as f:
    data = json.load(f)
if data.get("lock") == "codex":
    data["lock"] = None
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
        f.write("\n")
PY
}
trap cleanup EXIT

PROMPT="$(mktemp)"
cat > "$PROMPT" <<'EOF'
Read AGENTS.md, AI_TASK.md, AI_STATE.json, AI_HANDOFF.md, AI_CHANGELOG.md, AI_VERIFICATION.md, and AI_RISK_REGISTER.md.
Follow only AI_HANDOFF.md.
Never commit, push, merge, deploy, reset, clean, delete, or modify forbidden files.
Never start CP6 without explicit human approval.
EOF

codex exec --sandbox workspace-write --ask-for-approval on-request "$(cat "$PROMPT")"
