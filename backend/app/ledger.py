"""Read-only imported transactions. Never writes the virtual trading wallet."""

import csv, io, hashlib, json
from decimal import Decimal, InvalidOperation
from datetime import datetime, timezone
from fastapi import HTTPException
from app import trading
from app.store import now

COLUMNS = [
    "external_id",
    "symbol",
    "side",
    "qty",
    "price",
    "fees",
    "executed_at",
    "currency",
]


def parse_csv(text, mapping=None):
    if len(text.encode()) > 2_000_000:
        raise HTTPException(413, "CSV must be smaller than 2 MB")
    reader = csv.DictReader(io.StringIO(text.lstrip("\ufeff")))
    if not reader.fieldnames:
        raise HTTPException(422, "CSV has no header")
    mapping = mapping or {k: k for k in COLUMNS}
    rows = []
    errors = []
    for line, row in enumerate(reader, 2):
        if line > 10002:
            raise HTTPException(413, "Import at most 10,000 trades at once")
        try:
            get = lambda k, default="": (row.get(mapping.get(k, k)) or default).strip()
            sym = get("symbol").upper()
            side = get("side").upper()
            qty = Decimal(get("qty"))
            price = Decimal(get("price"))
            fees = Decimal(get("fees", "0"))
            if not sym or len(sym) > 40 or side not in ("BUY", "SELL"):
                raise ValueError("Symbol and BUY/SELL side required")
            if (
                not all(x.is_finite() for x in (qty, price, fees))
                or qty <= 0
                or price <= 0
                or fees < 0
            ):
                raise ValueError(
                    "Positive quantity/price and nonnegative fees required"
                )
            stamp = datetime.fromisoformat(get("executed_at").replace("Z", "+00:00"))
            if stamp.tzinfo is None:
                raise ValueError("executed_at must include a timezone")
            item = {
                "symbol": sym,
                "side": side,
                "qty": str(qty),
                "price": str(price),
                "fees": str(fees),
                "fees_known": bool(get("fees")),
                "executed_at": stamp.astimezone(timezone.utc).isoformat(),
                "currency": get("currency", "INR").upper(),
            }
            item["external_id"] = (
                get("external_id")
                or hashlib.sha256(json.dumps(item, sort_keys=True).encode()).hexdigest()
            )
            rows.append(item)
        except (ValueError, InvalidOperation, TypeError) as e:
            errors.append({"line": line, "error": str(e) or "Invalid numeric field"})
    return {
        "columns": reader.fieldnames,
        "mapping": mapping,
        "rows": rows,
        "errors": errors,
        "valid": not errors and bool(rows),
    }


def import_rows(db, owner, broker, rows):
    inserted = 0
    duplicates = 0
    updated = 0
    for row in rows:
        key = hashlib.sha256((broker + ":" + row["external_id"]).encode()).hexdigest()
        old = trading.get(db, owner, "imported_trade", key)
        data = {**row, "broker": broker}
        if old:
            previous = old.data
            same_core = all(
                Decimal(str(previous[k])) == Decimal(str(data[k]))
                if k in ("qty", "price")
                else previous.get(k) == data.get(k)
                for k in (
                    "symbol",
                    "side",
                    "qty",
                    "price",
                    "executed_at",
                    "currency",
                    "external_id",
                    "broker",
                )
            )
            old_known = previous.get(
                "fees_known", Decimal(str(previous.get("fees", 0))) > 0
            )
            new_known = data.get("fees_known", False)
            if same_core and new_known and not old_known:
                old.data = {
                    **previous,
                    "fees": data["fees"],
                    "fees_known": True,
                    "fee_updated_at": now(),
                }
                updated += 1
                continue
            if same_core and (
                not new_known
                or Decimal(str(previous["fees"])) == Decimal(str(data["fees"]))
            ):
                duplicates += 1
                continue
            raise HTTPException(
                409,
                "An existing source trade ID has conflicting values; no rows were committed",
            )
        trading.put(db, owner, "imported_trade", key, {**data, "imported_at": now()})
        inserted += 1
    batch = trading.ident()
    trading.put(
        db,
        owner,
        "import_batch",
        batch,
        {
            "id": batch,
            "broker": broker,
            "inserted": inserted,
            "duplicates": duplicates,
            "fees_updated": updated,
            "created_at": now(),
        },
    )
    return {
        "id": batch,
        "inserted": inserted,
        "duplicates": duplicates,
        "fees_updated": updated,
    }


def summarize(rows, reported=None):
    groups = {}
    realized = {}
    fees = {}
    issues = []
    for t in sorted(
        rows,
        key=lambda x: (
            x["executed_at"],
            0 if x["side"] == "BUY" else 1,
            x["external_id"],
        ),
    ):
        key = t["symbol"] + "|" + t["currency"]
        lots = groups.setdefault(key, [])
        qty = Decimal(t["qty"])
        price = Decimal(t["price"])
        fee = Decimal(t["fees"])
        ccy = t["currency"]
        fees[ccy] = fees.get(ccy, Decimal(0)) + fee
        if t["side"] == "BUY":
            lots.append({"qty": qty, "price": price, "fee_per_unit": fee / qty})
            continue
        remaining = qty
        profit = -fee
        while remaining > 0 and lots:
            lot = lots[0]
            matched = min(remaining, lot["qty"])
            profit += matched * (price - lot["price"] - lot["fee_per_unit"])
            remaining -= matched
            lot["qty"] -= matched
            if lot["qty"] == 0:
                lots.pop(0)
        if remaining > 0:
            issues.append(
                {
                    "symbol": t["symbol"],
                    "reason": "Sale exceeds imported buys. Import opening holdings/older history; short positions are not inferred.",
                    "unmatched_qty": str(remaining),
                }
            )
        else:
            realized[ccy] = realized.get(ccy, Decimal(0)) + profit
    holdings = []
    for key, lots in groups.items():
        sym, ccy = key.split("|")
        qty = sum((l["qty"] for l in lots), Decimal(0))
        cost = sum(
            (l["qty"] * (l["price"] + l["fee_per_unit"]) for l in lots), Decimal(0)
        )
        if qty:
            holdings.append(
                {
                    "symbol": sym,
                    "currency": ccy,
                    "qty": str(qty),
                    "cost": str(cost.quantize(Decimal(".01"))),
                    "avg_cost": str((cost / qty).quantize(Decimal(".01"))),
                }
            )
    mismatches = []
    for broker, snapshot in (reported or {}).items():
        for h in snapshot:
            actual = next(
                (Decimal(x["qty"]) for x in holdings if x["symbol"] == h["symbol"]),
                Decimal(0),
            )
            expected = Decimal(str(h["qty"]))
            if actual != expected:
                mismatches.append(
                    {
                        "broker": broker,
                        "symbol": h["symbol"],
                        "computed": str(actual),
                        "reported": str(expected),
                    }
                )
    return {
        "fee_status": "incomplete"
        if any(
            not t.get("fees_known", Decimal(str(t.get("fees", 0))) > 0) for t in rows
        )
        else "complete",
        "holdings": holdings,
        "realized_by_currency": {
            k: str(v.quantize(Decimal(".01"))) for k, v in realized.items()
        },
        "fees_by_currency": {k: str(v) for k, v in fees.items()},
        "issues": issues,
        "reconciliation": mismatches,
        "method": "FIFO; fees retained; currencies are not combined. Unsupported splits/bonuses and missing opening lots require reconciliation.",
    }
