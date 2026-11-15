"""Separate background process: refresh observations, process pending orders/alerts.
Run with PYTHONPATH=backend .venv/bin/python -m app.worker.
"""

import time, logging
from sqlalchemy import select
from app.store import DB, User, init, now
from app import market, trading
from app.main import evaluate_alerts

log = logging.getLogger("eye.worker")


def tick():
    try:
        status = market.refresh_quotes()
    except Exception:
        status = {
            "status": "error",
            "reason": "Operator feed unavailable; user connections and notification delivery continue independently",
        }

    try:
        market.refresh_public_crypto()
    except Exception:
        log.warning(
            "Public crypto observation refresh failed; previous observations expire normally"
        )
    with DB() as db:
        owners = list(db.scalars(select(User.id)))
    for owner in owners:
        from app.connections import refresh_user_quotes, credentials

        with DB() as read_db:
            connections = [
                (r.key, r.data) for r in trading.records(read_db, owner, "connection")
            ]
        for provider, connection in connections:
            try:
                refresh_user_quotes(owner, credentials(connection), provider)
            except Exception:
                with DB.begin() as error_db:
                    row = trading.get(error_db, owner, "connection", provider)
                    if row:
                        row.data = {
                            **row.data,
                            "quote_status": "error",
                            "error": "Provider refresh failed; check access-token expiry",
                            "last_attempt": now(),
                        }
                log.warning(
                    "User provider refresh failed; old observations expire normally"
                )
        with DB.begin() as db:
            db.scalar(select(User).where(User.id == owner).with_for_update())
            from app.investing import evaluate_owner
            evaluate_owner(db,owner)
            for r in trading.records(db, owner, "order"):
                o = dict(r.data)
                if o["scope"] != "paper" or o["status"] != "PENDING":
                    continue
                q = market.live_quote(o["symbol"], owner, db=db)
                if not q or not q.get("tradable", True):
                    continue
                hit = (
                    (q["price"] <= float(o["price"]))
                    if o["side"] == "BUY"
                    else (q["price"] >= float(o["price"]))
                )
                if hit:
                    acc = trading.account(db, owner)
                    acc.data = trading.execute(
                        trading.release(acc.data, o), o, q["price"]
                    )
                    r.data = {
                        **o,
                        "status": "FILLED",
                        "fill_price": float(trading.money(q["price"])),
                        "filled_at": q["observed_at"],
                        "source": q["source"],
                    }
            for instrument in market.catalog():
                q = market.live_quote(instrument["symbol"], owner, db=db)
                if not q and instrument.get("segment") == "funds":
                    q = market.latest(instrument["symbol"])
                if q:
                    evaluate_alerts(
                        db,
                        owner,
                        "paper",
                        instrument["symbol"],
                        q["price"],
                        q["observed_at"],
                    )
            for snapshot in trading.records(db, owner, "option_snapshot"):
                from app.connections import options

                try:
                    chain = options(db, owner, snapshot.key, snapshot.data["expiry"])
                    evaluate_alerts(
                        db, owner, "paper", snapshot.key, 0, chain["retrieved_at"]
                    )
                except Exception:
                    log.warning("Option alert refresh unavailable")
            trading.snapshot(db, owner)
            trading.put(
                db,
                "system",
                "worker",
                "status",
                {"observed_at": now(), "status": "healthy", "operator_feed": status},
            )
    from app.notifications import deliver_one

    for _ in range(10):
        if not deliver_one():
            break
    return status


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    init()
    import threading
    from app.live import stream_forever
    threading.Thread(target=stream_forever,name='provider-live-stream',daemon=True).start()
    while True:
        try:
            log.info("%s", tick())
        except Exception:
            log.exception(
                "Provider refresh failed; no synthetic fallback was generated"
            )
        time.sleep(30)
