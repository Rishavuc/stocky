import csv
import io
from datetime import datetime
from typing import List, Dict, Any, Optional
from app.schemas.schemas import UnifiedTradeItem

class TradeSyncService:
    def __init__(self):
        self.connected_brokers = [
            {"broker": "Zerodha Kite", "client_id": "AB1234", "status": "CONNECTED", "last_synced": "10 mins ago"},
            {"broker": "Upstox Pro", "client_id": "UP9876", "status": "CONNECTED", "last_synced": "1 hour ago"}
        ]
        self.trades: List[Dict] = [
            {"id": 1, "broker": "Zerodha", "source_trade_id": "ZRD-89101", "symbol": "RELIANCE", "segment": "EQ", "side": "BUY", "qty": 20, "price": 2750.00, "traded_at": "2026-10-01 10:14:00"},
            {"id": 2, "broker": "Zerodha", "source_trade_id": "ZRD-89102", "symbol": "TCS", "segment": "EQ", "side": "BUY", "qty": 15, "price": 3890.00, "traded_at": "2026-10-02 11:30:00"},
            {"id": 3, "broker": "Upstox", "source_trade_id": "UPS-44122", "symbol": "INFY", "segment": "EQ", "side": "BUY", "qty": 40, "price": 1470.00, "traded_at": "2026-10-05 14:15:00"},
            {"id": 4, "broker": "Upstox", "source_trade_id": "UPS-44123", "symbol": "INFY", "segment": "EQ", "side": "SELL", "qty": 20, "price": 1520.00, "traded_at": "2026-10-08 12:00:00"}
        ]

    def get_unified_trade_book(self, broker: Optional[str] = None) -> List[UnifiedTradeItem]:
        filtered = self.trades
        if broker and broker.lower() != "all":
            filtered = [t for t in self.trades if t["broker"].lower() == broker.lower()]

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
            for t in filtered
        ]

    def get_holdings_summary(self) -> Dict[str, Any]:
        # Aggregate trades to compute current portfolio
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
            "total_pnl_pct": round((unrealized / total_invested) * 100, 2),
            "holdings": holdings,
            "connected_brokers": self.connected_brokers
        }

    def import_csv_tradebook(self, csv_content: str, broker_name: str = "CSV Import") -> Dict[str, Any]:
        reader = csv.DictReader(io.StringIO(csv_content))
        imported_count = 0
        for row in reader:
            sym = row.get("Symbol") or row.get("symbol") or "N/A"
            side = row.get("Side") or row.get("side") or "BUY"
            qty = int(row.get("Qty") or row.get("qty") or 0)
            price = float(row.get("Price") or row.get("price") or 0.0)

            trade_id = f"CSV-{len(self.trades) + 1}"
            self.trades.insert(0, {
                "id": len(self.trades) + 1,
                "broker": broker_name,
                "source_trade_id": trade_id,
                "symbol": sym.upper(),
                "segment": "EQ",
                "side": side.upper(),
                "qty": qty,
                "price": price,
                "traded_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
            })
            imported_count += 1

        return {"success": True, "imported_trades": imported_count, "message": f"Successfully imported {imported_count} trades."}

    def connect_broker(self, broker_name: str, client_id: str) -> Dict[str, Any]:
        self.connected_brokers.append({
            "broker": broker_name,
            "client_id": client_id,
            "status": "CONNECTED",
            "last_synced": "Just now"
        })
        return {"success": True, "message": f"Successfully connected to {broker_name} account ({client_id})."}

trade_sync = TradeSyncService()
