#!/usr/bin/env bash
set -euo pipefail

# A bounded operator loop. The agent performs one action; Outcome OS remains the source of truth.
while true; do
  python outcome_os.py status
  if python outcome_os.py verify >/tmp/outcome-verdict.json 2>/dev/null; then
    cat /tmp/outcome-verdict.json
    echo "Goal verified complete."
    exit 0
  fi

  echo
  echo "=== NEXT WORK PROMPT ==="
  python outcome_os.py prompt work_prompt
  echo
  echo "After performing the action, record item status, evidence, checks, or blockers."
  echo "Then rerun this script."
  exit 2
done
