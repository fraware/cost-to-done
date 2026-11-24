#!/usr/bin/env bash
# Pinned Pi native Responses wire qualification, strictly mock-only.
set -Eeuo pipefail
cd "$(dirname "$0")/.."
root=$PWD
working=$(mktemp -d)
pid=''
cleanup() {
  rc=$?
  if [[ -n "$pid" ]]; then kill "$pid" 2>/dev/null || true; wait "$pid" 2>/dev/null || true; fi
  if (( rc != 0 )); then
    if [[ -f "$working/output" ]]; then tail -n 20 "$working/output" >&2; fi
    if [[ -f "$working/evidence.json" ]]; then cat "$working/evidence.json" >&2; fi
  fi
  rm -rf "$working"
}
trap cleanup EXIT
mkdir -p "$working/config" "$working/task" "$working/sessions"
cat > "$working/config/models.json" <<'JSON'
{
  "providers": {
    "cost-to-done-native-mock": {
      "baseUrl": "http://127.0.0.1:8879/v1",
      "apiKey": "ctd-native-wire-probe-token-00001",
      "api": "openai-responses",
      "models": [{"id": "test-model-1", "contextWindow": 8192, "maxTokens": 256, "reasoning": false}]
    }
  }
}
JSON
python3 -u tests/pi_wire/native_responses_mock.py --evidence "$working/evidence.json" --target "$working/task/sentinel.txt" &
pid=$!
for _ in $(seq 1 60); do
  if python3 -c 'import urllib.request; urllib.request.urlopen("http://127.0.0.1:8879/ready", timeout=0.5).close()' 2>/dev/null; then break; fi
  sleep 0.2
done
python3 -c 'import urllib.request; urllib.request.urlopen("http://127.0.0.1:8879/ready", timeout=2).close()'
(
  cd "$working/task"
  export PI_CODING_AGENT_DIR="$working/config"
  # No upstream secrets, only the local synthetic token in models.json.
  unset OPENAI_API_KEY ANTHROPIC_API_KEY GEMINI_API_KEY || true
  printf 'Use the write tool to write the requested sentinel file, then respond OK.\n' | timeout 90s pi --print --mode json \
    --session-dir "$working/sessions" --provider cost-to-done-native-mock --model test-model-1 \
    > "$working/output" 2>&1
)
python3 - "$working" <<'PY'
import json, sys
from pathlib import Path
p = Path(sys.argv[1])
assert (p / "task/sentinel.txt").read_text() == "native-responses-wire-ok\n"
requests = json.loads((p / "evidence.json").read_text())
assert len(requests) == 2, len(requests)
assert "function_call_output" in requests[1]["input_types"], requests[1]["input_types"]
# A valid tool effect alone is insufficient; check Pi's terminal agent event.
events = [json.loads(line) for line in (p / "output").read_text().splitlines()
          if line.startswith("{")]
messages = [m for event in events if event.get("type") == "agent_end"
            for m in event.get("messages", []) if m.get("role") == "assistant"]
assert messages, "missing terminal assistant message"
assert any(part.get("type") == "text" and part.get("text", "").strip() == "OK"
           for part in messages[-1].get("content", [])), "missing final OK"
assert messages[-1].get("stopReason") == "stop", messages[-1].get("stopReason")
print(json.dumps(requests, indent=2))
print("PASS: pinned Pi native Responses mock tool execution and matched continuation")
PY
