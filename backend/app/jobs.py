"""Independent scheduled market refresh/training process with persistent status."""

import os, sys, time, subprocess
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
from app.store import DB, init, now
from app import trading, market


def _once(force=False):
    stamp = datetime.now(ZoneInfo("Asia/Kolkata"))
    key = stamp.date().isoformat()
    with DB.begin() as db:
        old = trading.get(db, "system", "job", "market-model-refresh")
        if not force:
            if stamp.hour < 17:
                return
            if old and old.data.get("date") == key:
                d = old.data
                if d.get("status") == "completed":
                    return
                if d.get("status") == "running" and d.get("lease_until", "") > now():
                    return
                if d.get("status") == "failed" and (
                    d.get("attempts", 0) >= 3 or d.get("retry_after", "") > now()
                ):
                    return
        attempts = (
            old.data.get("attempts", 0) if old and old.data.get("date") == key else 0
        ) + 1
        trading.put(
            db,
            "system",
            "job",
            "market-model-refresh",
            {
                "name": "market-model-refresh",
                "date": key,
                "status": "running",
                "started_at": now(),
                "attempts": attempts,
                "lease_until": (
                    datetime.now(timezone.utc) + timedelta(hours=2)
                ).isoformat(),
            },
        )
    root = market.ROOT
    log = root / "runtime/jobs.log"
    log.parent.mkdir(exist_ok=True)
    try:
        with log.open("a") as out:
            subprocess.run(
                [sys.executable, str(root / "scripts/refresh_markets.py")],
                cwd=root,
                stdout=out,
                stderr=out,
                check=True,
            )
            subprocess.run(
                [sys.executable, "-m", "app.research"],
                cwd=root,
                env={
                    **os.environ,
                    "PYTHONPATH": str(root / "backend"),
                    "OMP_NUM_THREADS": "2",
                },
                stdout=out,
                stderr=out,
                check=True,
            )
        status = "completed"
        error = None
    except Exception:
        status = "failed"
        error = "Refresh or training failed; inspect runtime/jobs.log. Last valid versions remain available."
    with DB.begin() as db:
        trading.put(
            db,
            "system",
            "job",
            "market-model-refresh",
            {
                "name": "market-model-refresh",
                "date": key,
                "status": status,
                "finished_at": now(),
                "error": error,
                "attempts": attempts,
                "retry_after": (
                    datetime.now(timezone.utc) + timedelta(minutes=30)
                ).isoformat(),
            },
        )

    if status == "completed":
        backup_status = "completed"
        backup_error = None
        try:
            with log.open("a") as out:
                subprocess.run(
                    [sys.executable, str(root / "scripts/backup.py")],
                    cwd=root,
                    stdout=out,
                    stderr=out,
                    check=True,
                )
        except Exception:
            backup_status = "failed"
            backup_error = "Backup failed; model refresh remains completed. Inspect runtime/jobs.log."
        with DB.begin() as db:
            trading.put(
                db,
                "system",
                "job",
                "encrypted-backup",
                {
                    "name": "encrypted-backup",
                    "date": key,
                    "status": backup_status,
                    "error": backup_error,
                    "finished_at": now(),
                },
            )


def once(force=False):
    import fcntl

    path = market.ROOT / "runtime/scheduler.lock"
    path.parent.mkdir(exist_ok=True)
    with path.open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return
        try:
            return _once(force)
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


def fast_cycle():
    """Refresh completed intraday/hourly bars and infer with existing weights."""
    import fcntl

    path = market.ROOT / "runtime/inference.lock"
    path.parent.mkdir(exist_ok=True)
    with path.open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return
        stamp = datetime.now(ZoneInfo("Asia/Kolkata"))
        bucket = stamp.strftime("%Y-%m-%dT%H:") + str(stamp.minute // 5)
        with DB.begin() as db:
            old = trading.get(db, "system", "job", "bar-inference")
            if old and old.data.get("bucket") == bucket:
                return
            trading.put(
                db,
                "system",
                "job",
                "bar-inference",
                {
                    "name": "bar-inference",
                    "bucket": bucket,
                    "status": "running",
                    "started_at": now(),
                },
            )
        try:
            sys.path.insert(0, str(market.ROOT / "scripts"))
            from refresh_markets import yahoo, binance, STOCKS
            from app.datasets import publish
            from app.research import infer, outcomes

            updates = []
            symbols = []
            if (
                stamp.weekday() < 5
                and 9 * 60 + 20 <= stamp.hour * 60 + stamp.minute <= 15 * 60 + 40
            ):
                for symbol in ("RELIANCE", "TCS"):
                    try:
                        updates.append(yahoo(symbol, STOCKS[symbol], "equities", "5m"))
                        symbols.append(symbol + "_5m")
                    except Exception:
                        pass
            for pair in ("BTCUSDT", "ETHUSDT", "SOLUSDT"):
                try:
                    updates.append(binance(pair, "1h"))
                    symbols.append(pair + "_1h")
                except Exception:
                    pass
            if updates:
                publish(updates)
            updated = 0
            for symbol in symbols:
                horizons = (3,) if symbol.endswith("_5m") else (1, 24)
                for horizon in horizons:
                    if infer(symbol, horizon):
                        updated += 1
            outcomes()
            status = {
                "status": "completed",
                "datasets": len(updates),
                "inferences": updated,
                "finished_at": now(),
            }
        except Exception:
            status = {
                "status": "failed",
                "error": "Bar refresh/inference failed; previous valid artifacts retained",
                "finished_at": now(),
            }
        with DB.begin() as db:
            trading.put(
                db,
                "system",
                "job",
                "bar-inference",
                {"name": "bar-inference", "bucket": bucket, **status},
            )
        fcntl.flock(lock, fcntl.LOCK_UN)


if __name__ == "__main__":
    init()
    while True:
        once()
        fast_cycle()
        time.sleep(60)
