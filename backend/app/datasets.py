"""Content-addressed history, atomically published catalogs, and pinned replay inputs."""

import csv
import hashlib
import io
import json
import os
import tempfile
from pathlib import Path
from fastapi import HTTPException

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data/history"


def atomic(path, content):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix="publish-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(content if isinstance(content, bytes) else content.encode())
            f.flush()
            os.fsync(f.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def freeze(symbol, content):
    digest = hashlib.sha256(content).hexdigest()
    path = DATA / "versions" / symbol / (digest + ".csv")
    if not path.exists():
        atomic(path, content)
    return digest


def ensure_versions():
    manifest = DATA / "manifest.json"
    if not manifest.exists():
        return
    for m in json.loads(manifest.read_text()):
        path = DATA / (m["symbol"] + ".csv")
        if path.exists():
            freeze(m["symbol"], path.read_bytes())


def read(symbol, version=None):
    if not symbol.replace("-", "").replace("_", "").isalnum():
        raise HTTPException(404, "Unknown instrument")
    manifest = json.loads((DATA / "manifest.json").read_text())
    m = next((x for x in manifest if x["symbol"] == symbol), None)
    if not m:
        raise HTTPException(404, "Unknown instrument")
    digest = version or m["sha256"]
    if len(digest) != 64 or any(x not in "0123456789abcdef" for x in digest):
        raise HTTPException(422, "Invalid dataset version")
    path = DATA / "versions" / symbol / (digest + ".csv")
    if not path.exists():
        legacy = DATA / (symbol + ".csv")
        if (
            legacy.exists()
            and hashlib.sha256(legacy.read_bytes()).hexdigest() == digest
        ):
            return legacy.read_bytes()
        raise HTTPException(
            409,
            "The pinned dataset is unavailable; restore its archive before continuing this session",
        )
    content = path.read_bytes()
    if hashlib.sha256(content).hexdigest() != digest:
        raise HTTPException(503, "Dataset checksum mismatch")
    return content


def _publish(updates):
    """Failures retain the old instrument and every replay's immutable inputs."""
    ensure_versions()
    path = DATA / "manifest.json"
    old = (
        {m["symbol"]: m for m in json.loads(path.read_text())} if path.exists() else {}
    )
    for metadata, content in updates:
        symbol = metadata["symbol"]
        digest = freeze(symbol, content)
        rows = list(csv.DictReader(io.StringIO(content.decode())))
        if not rows:
            raise ValueError("Cannot publish empty history")
        old[symbol] = {
            **metadata,
            "sha256": digest,
            "rows": len(rows),
            "start": rows[0]["date"],
            "end": rows[-1]["date"],
        }
        atomic(DATA / (symbol + ".csv"), content)  # Compatibility for training scripts.
    atomic(path, json.dumps(list(old.values()), indent=2))
    return list(old.values())


def publish(updates):
    import fcntl
    DATA.mkdir(parents=True,exist_ok=True)
    with (DATA/'.publish.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        try:return _publish(updates)
        finally:fcntl.flock(lock,fcntl.LOCK_UN)
