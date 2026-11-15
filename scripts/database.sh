#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
PG_BIN=${EYE_PG_BIN:-/opt/homebrew/opt/postgresql@17/bin}
ROOT_DIR=$PWD
DATA_DIR="$ROOT_DIR/runtime/postgres"
mkdir -p runtime
case "${1:-start}" in
 start)
  if [[ ! -f "$DATA_DIR/PG_VERSION" ]]; then
    .venv/bin/python - <<'PY'
import secrets,os
p='runtime/pg-password'
fd=os.open(p,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
with os.fdopen(fd,'w') as f:f.write(secrets.token_hex(24))
PY
    "$PG_BIN/initdb" -D "$DATA_DIR" -U eye_admin --auth-local=trust --auth-host=scram-sha-256 --pwfile=runtime/pg-password --encoding=UTF8 --no-locale >/dev/null
  fi
  if ! "$PG_BIN/pg_ctl" -D "$DATA_DIR" status >/dev/null 2>&1; then
    "$PG_BIN/pg_ctl" -D "$DATA_DIR" -l "$ROOT_DIR/runtime/postgres.log" -o "-h 127.0.0.1 -p 55432 -k $ROOT_DIR/runtime" start
  fi
  export EYE_PG_BIN="$PG_BIN"
  .venv/bin/python - <<'PYSQL'
from pathlib import Path
import subprocess,os
password=Path('runtime/pg-password').read_text().strip()
cmd=[os.environ['EYE_PG_BIN']+'/psql','-h',str(Path('runtime').resolve()),'-p','55432','-U','eye_admin','-d','postgres','-v','ON_ERROR_STOP=1']
query="SELECT 1 FROM pg_roles WHERE rolname='eye';"
exists=subprocess.run(cmd+['-tAc',query],capture_output=True,text=True,check=True).stdout.strip()
if not exists:
 subprocess.run(cmd,input="CREATE ROLE eye LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE PASSWORD '"+password+"';\n",text=True,check=True,stdout=subprocess.DEVNULL)
PYSQL
  if ! "$PG_BIN/psql" -h "$ROOT_DIR/runtime" -p 55432 -U eye_admin -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname='investorseye'" | rg -q '^1$'; then
    "$PG_BIN/createdb" -h "$ROOT_DIR/runtime" -p 55432 -U eye_admin -O eye investorseye
  fi
  if [[ ! -f .env ]]; then
    .venv/bin/python - <<'PY'
from pathlib import Path
import os
password=Path('runtime/pg-password').read_text().strip()
fd=os.open('.env',os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
with os.fdopen(fd,'w') as f:
 f.write('DATABASE_URL=postgresql+psycopg://eye:'+password+'@127.0.0.1:55432/investorseye\nPOSTGRES_PASSWORD='+password+'\nCOOKIE_SECURE=false\nAPP_HOST=127.0.0.1\nAPP_PORT=8000\nALLOWED_ORIGINS=http://127.0.0.1:8000,http://localhost:8000\n')
PY
  fi
  echo 'Project PostgreSQL is ready on localhost:55432.'
 ;;
 stop) "$PG_BIN/pg_ctl" -D "$DATA_DIR" stop ;;
 status) "$PG_BIN/pg_ctl" -D "$DATA_DIR" status ;;
 *) echo 'Usage: scripts/database.sh start|stop|status'; exit 2 ;;
esac
