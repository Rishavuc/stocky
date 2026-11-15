"""Encrypted PostgreSQL backup and optional isolated restore verification."""

import os, sys, subprocess, json, hashlib, tempfile, secrets, shutil
from pathlib import Path
from datetime import datetime, timezone
from urllib.parse import urlparse, unquote, parse_qs
import psycopg

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from dotenv import load_dotenv

load_dotenv(ROOT / ".env")
from app.connections import cipher

u = urlparse(os.environ["DATABASE_URL"].replace("+psycopg", ""))
pg = (
    os.getenv("EYE_PG_BIN") or str(Path(shutil.which("pg_dump")).parent)
    if shutil.which("pg_dump")
    else os.getenv("EYE_PG_BIN", "/opt/homebrew/opt/postgresql@17/bin")
)
env = {
    **os.environ,
    "PGPASSWORD": unquote(u.password or ""),
    "PGSSLMODE": parse_qs(u.query).get("sslmode", ["prefer"])[0],
}
args = [
    "-h",
    u.hostname or "localhost",
    "-p",
    str(u.port or 5432),
    "-U",
    u.username or "eye",
]
db = u.path.lstrip("/")
folder = ROOT / "runtime/backups"
folder.mkdir(parents=True, exist_ok=True)
stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
# The verification counts and pg_dump share one exported MVCC snapshot.
# Live worker writes cannot make a valid backup appear inconsistent.
with psycopg.connect(
    os.environ["DATABASE_URL"].replace("+psycopg", ""), autocommit=True
) as source:
    with source.transaction():
        source.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        snapshot = source.execute("SELECT pg_export_snapshot()").fetchone()[0]
        expected = [
            source.execute("SELECT count(*) FROM " + table).fetchone()[0]
            for table in ("eye_users", "eye_records", "eye_schema_migrations")
        ]
        raw = subprocess.run(
            [pg + "/pg_dump", *args, "-Fc", "--snapshot=" + snapshot, db],
            env=env,
            capture_output=True,
            check=True,
        ).stdout
path = folder / (stamp + "-" + secrets.token_hex(3) + ".dump.enc")
fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
with os.fdopen(fd, "wb") as f:
    f.write(cipher().encrypt(raw))
print("Encrypted backup created:", path.name)
if "--verify" in sys.argv:
    target = "eye_restore_check_" + secrets.token_hex(5)
    socket = str(ROOT / "runtime")
    admin = ["-h", socket, "-p", str(u.port or 5432), "-U", "eye_admin"]
    subprocess.run([pg + "/createdb", *admin, "-O", u.username, target], check=True)
    try:
        restored = cipher().decrypt(path.read_bytes())
        subprocess.run(
            [pg + "/pg_restore", *args, "--no-owner", "--exit-on-error", "-d", target],
            env=env,
            input=restored,
            check=True,
            capture_output=True,
        )
        sql = "SELECT count(*) FROM eye_users; SELECT count(*) FROM eye_records; SELECT count(*) FROM eye_schema_migrations;"
        after = subprocess.run(
            [pg + "/psql", *args, "-d", target, "-tAc", sql],
            env=env,
            capture_output=True,
            text=True,
            check=True,
        ).stdout
        assert expected == [int(n) for n in after.split()], (
            "Restore row counts differ from the exported backup snapshot"
        )
        print("PASS: isolated restore recovered users, owned records and migrations.")
    finally:
        subprocess.run([pg + "/dropdb", *admin, target], check=True)
