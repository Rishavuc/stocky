#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
source scripts/process.sh
for process in server worker jobs; do
  if [[ -f runtime/$process.pid ]]; then
    pattern="app.$process"
    [[ "$process" == server ]] && pattern="backend/run.py"
    if eye_process_matches "$(cat "runtime/$process.pid")" "$pattern"; then kill "$(cat "runtime/$process.pid")" 2>/dev/null || true; fi
    rm -f "runtime/$process.pid"
  fi
done
echo 'Workspace processes stopped. The project database remains available.'
