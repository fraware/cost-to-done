#!/usr/bin/env bash
# Capture the actual request emitted by pinned Pi against a mock API.
set -Eeuo pipefail
cd "$(dirname "$0")/.."
command -v pi >/dev/null || { echo 'Pi CLI is missing; install pinned @earendil-works/pi-coding-agent@0.85.1' >&2; exit 2; }
command -v python3 >/dev/null
working=$(mktemp -d)
server_pid=''
cleanup() {
  rc=$?
  if [[ -n "$server_pid" ]]; then kill "$server_pid" 2>/dev/null || true; wait "$server_pid" 2>/dev/null || true; fi
  if (( rc != 0 )); then
    echo 'Pi mock wire test failed; see captured process output below' >&2
    if [[ -f "$working/pi-output.txt" ]]; then tail -n 30 "$working/pi-output.txt" >&2; fi
  fi
  rm -rf "$working"
}
trap cleanup EXIT

python3 -u tests/pi_wire/mock_api.py --output "$working/request.json" &
server_pid=$!
for _ in $(seq 1 60); do
  if python3 -c 'import urllib.request; urllib.request.urlopen("http://127.0.0.1:8877/ready",timeout=0.5).close()' 2>/dev/null; then break; fi
  sleep 0.2
done
python3 -c 'import urllib.request; urllib.request.urlopen("http://127.0.0.1:8877/ready",timeout=2).close()'

mkdir -p "$working/isolated-pi-config" "$working/sessions"
cat > "$working/isolated-pi-config/models.json" <<'JSON'
{
  "providers": {
    "cost-to-done-mock": {
      "baseUrl": "http://127.0.0.1:8877/v1",
      "apiKey": "mock-pi-only-token",
      "api": "openai-completions",
      "models": [{"id": "test-model-1", "contextWindow": 8192, "maxTokens": 256}]
    }
  }
}
JSON
export PI_CODING_AGENT_DIR="$working/isolated-pi-config"
printf 'Respond with OK. Do not use tools.\n' | timeout 90s pi --print --mode json \
  --session-dir "$working/sessions" --provider cost-to-done-mock --model test-model-1 \
  > "$working/pi-output.txt" 2>&1

python3 - "$working/request.json" <<'PY'
import json, sys
from pathlib import Path
p=Path(sys.argv[1])
assert p.is_file(), 'Pi did not send any request to the mock Chat Completions endpoint'
r=json.loads(p.read_text())
assert r['model']=='test-model-1', r.get('model')
assert isinstance(r.get('messages'),list) and r['messages'], 'missing conversation'
assert 'tools' in r and isinstance(r['tools'],list), 'Pi did not supply coding-agent tools'
print('Pinned Pi actual request keys:', ', '.join(sorted(r)))
print('Streaming:', r.get('stream'))
print('Maximum output tokens:',r.get('max_completion_tokens',r.get('max_tokens')))
print('Supplied tool declarations:',len(r['tools']))
print('Wire compatibility observation only; no provider charge or repair outcome was measured')
PY
