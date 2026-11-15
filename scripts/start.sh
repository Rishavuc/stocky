#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
source scripts/process.sh
if [[ -f runtime/server.pid ]] && eye_process_matches "$(cat runtime/server.pid)" "backend/run.py"; then
  echo 'InvestorsEYE is already running. Open http://127.0.0.1:8000.'
  exit 0
fi
if [[ -f runtime/postgres/PG_VERSION ]]; then scripts/database.sh start; fi
if [[ -f .env ]]; then set -a; source .env; set +a; fi
if [[ ! -f frontend/dist/index.html ]]; then npm --prefix frontend ci; npm --prefix frontend run build; fi
if [[ ! -f data/history/manifest.json ]]; then .venv/bin/python scripts/fetch_history.py; fi
if [[ ! -f models/RELIANCE_1_report.json ]]; then PYTHONPATH=backend OMP_NUM_THREADS=2 .venv/bin/python -m app.research; fi
mkdir -p runtime
WORKER_STARTED=false
JOBS_STARTED=false
if [[ -f runtime/worker.pid ]] && eye_process_matches "$(cat runtime/worker.pid)" "app.worker"; then
  echo 'Worker is already running.'
else
  PYTHONPATH=backend .venv/bin/python -m app.worker >runtime/worker.log 2>&1 &
  echo $! >runtime/worker.pid
  WORKER_STARTED=true
fi
if [[ ! -f runtime/jobs.pid ]] || ! eye_process_matches "$(cat runtime/jobs.pid)" "app.jobs"; then
  PYTHONPATH=backend .venv/bin/python -m app.jobs >runtime/scheduler.log 2>&1 &
  echo $! >runtime/jobs.pid
  JOBS_STARTED=true
fi
.venv/bin/python backend/run.py &
WEB_PID=$!
echo "$WEB_PID" >runtime/server.pid
cleanup() {
  kill "$WEB_PID" 2>/dev/null || true
  rm -f runtime/server.pid
  if [[ "$JOBS_STARTED" == true ]]; then kill "$(cat runtime/jobs.pid)" 2>/dev/null || true; rm -f runtime/jobs.pid; fi
  if [[ "$WORKER_STARTED" == true ]]; then
    kill "$(cat runtime/worker.pid)" 2>/dev/null || true
    rm -f runtime/worker.pid
  fi
}
trap cleanup EXIT
trap 'exit 0' INT TERM
wait "$WEB_PID"
