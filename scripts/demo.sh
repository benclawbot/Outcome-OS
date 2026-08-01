#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DEMO="${TMPDIR:-/tmp}/outcome-os-demo"
rm -rf "$DEMO"
mkdir -p "$DEMO"
cd "$DEMO"
python "$ROOT/outcome_os.py" init "Verified demo" --objective "Demonstrate evidence-based completion" --criterion "Artifact exists" --criterion "Test passes"
python "$ROOT/outcome_os.py" add-item "Create artifact" --priority 100
ITEM="$(python - <<'PY'
import json
print(json.load(open('.outcome-os/state.json'))['work_items'][0]['id'])
PY
)"
readarray -t CRITERIA < <(python - <<'PY'
import json
for item in json.load(open('.outcome-os/state.json'))['criteria']:
    print(item['id'])
PY
)
touch artifact.txt
python "$ROOT/outcome_os.py" evidence "${CRITERIA[0]}" "artifact.txt" --type file
python "$ROOT/outcome_os.py" evidence "${CRITERIA[1]}" "unit test output: OK" --type test
python "$ROOT/outcome_os.py" check demo pass --details "Demonstration check passed"
python "$ROOT/outcome_os.py" set-item "$ITEM" done
python "$ROOT/outcome_os.py" verify
python "$ROOT/outcome_os.py" dashboard
python "$ROOT/outcome_os.py" doctor
