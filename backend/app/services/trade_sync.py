import copy
import csv
import io
import itertools
import math
from datetime import datetime
from typing import List, Dict, Any, Optional
from app.schemas.schemas import UnifiedTradeItem

MAX_TRADES_PER_USER = 5000
MAX_BROKERS_PER_USER = 10
MAX_CSV_ROWS = 2000

# Demo rows every new user starts with (the UI shows a sample book).
_DEMO_BROKERS = [
    {"broker": "Zerodha Kite", "client_id": "AB1234", "status": "CONNECTED", "last_synced": "10 mins ago"},
    {"broker": "Upstox Pro", "client_id": "UP9876", "status": "CONNECTED", "last_synced": "1 hour ago"}
]
_DEMO_TRADES = [
    {"broker": "Zerodha", "source_trade_id": "ZRD-89101", "symbol": "RELIANCE", "segment": "EQ", "side": "BUY", "qty": 20, "price": 2750.00, "traded_at": "2026-10-01 10:14:00"},
    {"broker": "Zerodha", "source_trade_id": "ZRD-89102", "symbol": "TCS", "segment": "EQ", "side": "BUY", "qty": 15, "price": 3890.00, "traded_at": "2026-10-02 11:30:00"},
    {"broker": "Upstox", "source_trade_id": "UPS-44122", "symbol": "INFY", "segment": "EQ", "side": "BUY", "qty": 40, "price": 1470.00, "traded_at": "2026-10-05 14:15:00"},
    {"broker": "Upstox", "source_trade_id": "UPS-44123", "symbol": "INFY", "segment": "EQ", "side": "SELL", "qty": 20, "price": 1520.00, "traded_at": "2026-10-08 12:00:00"}
]


class TradeSyncService:
    """In-memory trade book, one per signed-in user (resets on restart)."""

    def __init__(self):
        self._books: Dict[str, Dict[str, List[Dict]]] = {}
        self._ids = itertools.count(1)

    def _book(self, user_id: str) -> Dict[str, List[Dict]]:
        book = self._books.get(user_id)
        if book is None:
            trades = [{"id": next(self._ids), **t} for t in _DEMO_TRADES]
            book = {"brokers": copy.deepcopy(_DEMO_BROKERS), "trades": trades}
            self._books[user_id] = book
        return book

    def get_unified_trade_book(self, user_id: str, broker: Optional[str] = None) -> List[UnifiedTradeItem]:
        trades = self._book(user_id)["trades"]
        if broker and broker.lower() != "all":
            trades = [t for t in trades if t["broker"].lower() == broker.lower()]

        return [
            UnifiedTradeItem(
                id=t["id"],
                broker=t["broker"],
                symbol=t["symbol"],
                segment=t["segment"],
                side=t["side"],
                qty=t["qty"],
                price=t["price"],
                traded_at=t["traded_at"]
            )
            for t in trades
        ]

    def get_holdings_summary(self, user_id: str) -> Dict[str, Any]:
        # Sample holdings (demo data, not computed from the trade book yet).
        holdings = {
            "RELIANCE": {"qty": 20, "avg_cost": 2750.00, "broker": "Zerodha", "current_price": 2890.40},
            "TCS": {"qty": 15, "avg_cost": 3890.00, "broker": "Zerodha", "current_price": 3940.15},
            "INFY": {"qty": 20, "avg_cost": 1470.00, "broker": "Upstox", "current_price": 1520.30}
        }
        total_invested = sum(h["qty"] * h["avg_cost"] for h in holdings.values())
        current_value = sum(h["qty"] * h["current_price"] for h in holdings.values())
        unrealized = current_value - total_invested

        return {
            "total_invested": round(total_invested, 2),
            "current_value": round(current_value, 2),
            "total_pnl": round(unrealized, 2),
            "total_pnl_pct": round((unrealized / total_invested) * 100, 2) if total_invested else 0.0,
            "holdings": holdings,
            "connected_brokers": list(self._book(user_id)["brokers"])
        }

    @staticmethod
    def _parse_row(row: Dict[str, Optional[str]]) -> Optional[Dict[str, Any]]:
        """Returns a clean trade, or None when the row is unusable."""
        sym = (row.get("Symbol") or row.get("symbol") or "").strip().upper()
        side = (row.get("Side") or row.get("side") or "BUY").strip().upper()
        try:
            qty = int(float(row.get("Qty") or row.get("qty") or 0))
            price = float(row.get("Price") or row.get("price") or 0.0)
        except (TypeError, ValueError):
            return None
        if not sym or len(sym) > 30 or side not in ("BUY", "SELL"):
            return None
        if qty <= 0 or not math.isfinite(price) or price <= 0:
            return None
        return {"symbol": sym, "side": side, "qty": qty, "price": round(price, 4)}

    def import_csv_tradebook(self, user_id: str, csv_content: str, broker_name: str = "CSV Import") -> Dict[str, Any]:
        trades = self._book(user_id)["trades"]
        reader = csv.DictReader(io.StringIO(csv_content))
        imported_count = 0
        skipped = 0
        now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        for i, row in enumerate(reader):
            if i >= MAX_CSV_ROWS or len(trades) >= MAX_TRADES_PER_USER:
                skipped += 1
                continue
            parsed = self._parse_row(row)
            if parsed is None:
                skipped += 1
                continue
            trade_id = next(self._ids)
            trades.insert(0, {
                "id": trade_id,
                "broker": broker_name,
                "source_trade_id": f"CSV-{trade_id}",
                "segment": "EQ",
                "traded_at": now,
                **parsed,
            })
            imported_count += 1

        msg = f"Successfully imported {imported_count} trades."
        if skipped:
            msg += f" Skipped {skipped} invalid or over-limit rows."
        return {"success": True, "imported_trades": imported_count, "skipped_rows": skipped, "message": msg}

    def connect_broker(self, user_id: str, broker_name: str, client_id: str) -> Dict[str, Any]:
        brokers = self._book(user_id)["brokers"]
        if len(brokers) >= MAX_BROKERS_PER_USER:
            raise ValueError(f"You can connect at most {MAX_BROKERS_PER_USER} broker accounts.")
        brokers.append({
            "broker": broker_name,
            "client_id": client_id,
            "status": "CONNECTED",
            "last_synced": "Just now"
        })
        return {"success": True, "message": f"Successfully connected to {broker_name} account ({client_id})."}

trade_sync = TradeSyncService()
