import json
import math
import os
import threading
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

from app.services.market_ingest import market_ingest
from app.schemas.schemas import PaperOrderRequest, PaperPortfolioResponse, PaperPositionResponse


DEFAULT_STATE_PATH = Path(__file__).resolve().parents[2] / "data" / "paper_portfolio.json"
DEFAULT_LEDGER_EPOCH = "initial"


class PaperTradingEngine:
    """Persistent paper-trading ledger.

    Positions stay open until they are sold or squared off, including across
    page refreshes and server restarts. The JSON file is the source of truth;
    localStorage in the browser is only a UI cache.
    """

    def __init__(self):
        self.initial_capital: float = 1000000.0
        self.cash: float = self.initial_capital
        self.realized_pnl: float = 0.0
        self.positions: Dict[str, Dict] = {}
        self.orders: List[Dict] = []
        self.ledger_epoch: str = DEFAULT_LEDGER_EPOCH
        self._lock = threading.RLock()
        self._state_path = Path(os.getenv("PAPER_PORTFOLIO_FILE", str(DEFAULT_STATE_PATH)))
        self._load_state()

    # ------------------------------------------------------------
    # PERSISTENCE
    # ------------------------------------------------------------
    @staticmethod
    def _identity_value(order: Dict, key: str) -> str:
        item = order.get(key, "")
        if item is None:
            return ""
        text = str(item)
        if key == "pnl" and text.strip() in ("0", "0.0", "0.00", "null", "None"):
            return ""
        return text

    @classmethod
    def _order_identity(cls, order: Dict) -> str:
        """Stable id for orders saved before client_order_id existed."""
        raw = "|".join(cls._identity_value(order, key) for key in (
            "time", "side", "symbol", "product", "qty", "price", "status", "pnl"
        ))
        h = 2166136261
        for ch in raw:
            h = ((h ^ ord(ch)) * 16777619) & 0xFFFFFFFF
        return f"legacy-{h:08x}"

    @classmethod
    def _request_identity(cls, order: Dict) -> str:
        """Time-independent identity used to reject stale client replays."""
        raw = "|".join(cls._identity_value(order, key) for key in (
            "side", "symbol", "product", "qty", "price", "status", "pnl"
        ))
        h = 2166136261
        for ch in raw:
            h = ((h ^ ord(ch)) * 16777619) & 0xFFFFFFFF
        return f"request-{h:08x}"

    def _find_existing_order(
        self,
        client_order_id: Optional[str],
        candidate: Optional[Dict] = None
    ) -> Optional[Dict]:
        """Idempotency lookup used when replaying offline/local orders."""
        cid = str(client_order_id).strip() if client_order_id else ""
        candidate_identity = (
            self._request_identity(candidate)
            if candidate and (not cid or cid.startswith("legacy-"))
            else None
        )
        for order in self.orders:
            if cid and order.get("client_order_id") == cid:
                return order
            if candidate_identity and self._request_identity(order) == candidate_identity:
                return order
        return None

    def _load_state(self) -> None:
        try:
            if not self._state_path.exists():
                return
            data = json.loads(self._state_path.read_text(encoding="utf-8"))
            epoch = data.get("epoch") or data.get("ledger_epoch") or DEFAULT_LEDGER_EPOCH
            self.ledger_epoch = str(epoch)
            cash = float(data.get("cash", self.initial_capital))
            if math.isfinite(cash):
                self.cash = cash
            realized = float(data.get("realized_pnl", 0.0))
            if math.isfinite(realized):
                self.realized_pnl = realized

            saved_positions = data.get("positions") or {}
            if isinstance(saved_positions, dict):
                for pos in saved_positions.values():
                    try:
                        sym = str(pos.get("symbol") or "").upper().strip()
                        prod = str(pos.get("product") or "CNC").upper().strip()
                        qty = float(pos.get("qty") or 0)
                        buy_price = float(pos.get("buy_price") or 0)
                        if sym and qty > 0 and buy_price > 0:
                            self.positions[f"{sym}_{prod}"] = {
                                "symbol": sym,
                                "product": prod,
                                "qty": qty,
                                "buy_price": buy_price,
                            }
                    except (TypeError, ValueError):
                        continue

            saved_orders = data.get("orders") or []
            if isinstance(saved_orders, list):
                restored_orders: List[Dict] = []
                for order in saved_orders:
                    if not isinstance(order, dict) or not order.get("symbol"):
                        continue
                    item = dict(order)
                    if not item.get("client_order_id"):
                        item["client_order_id"] = self._order_identity(item)
                    if not item.get("created_at"):
                        item["created_at"] = str(item.get("time") or "")
                    restored_orders.append(item)
                self.orders = restored_orders[:200]
        except Exception as e:
            print(f"[Paper Trading] Could not load saved portfolio: {e}")

    def _save_state(self) -> None:
        try:
            self._state_path.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "epoch": self.ledger_epoch,
                "cash": self.cash,
                "realized_pnl": self.realized_pnl,
                "positions": self.positions,
                "orders": self.orders,
                "saved_at": datetime.utcnow().isoformat() + "Z",
            }
            tmp = self._state_path.with_name(self._state_path.name + ".tmp")
            tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            os.replace(tmp, self._state_path)
        except Exception as e:
            print(f"[Paper Trading] Could not persist portfolio: {e}")

    # ------------------------------------------------------------
    # PORTFOLIO
    # ------------------------------------------------------------
    def get_portfolio(self) -> PaperPortfolioResponse:
        with self._lock:
            positions_res: List[PaperPositionResponse] = []
            holdings_val = 0.0
            unrealized_pnl = 0.0
            margin_used = 0.0

            for key, pos in self.positions.items():
                sym = pos["symbol"]
                qty = pos["qty"]
                buy_price = pos["buy_price"]
                quote = market_ingest.get_quote(sym)
                ltp = quote.price if quote else buy_price

                cur_val = round(ltp * qty, 2)
                cost_val = round(buy_price * qty, 2)
                pnl = round(cur_val - cost_val, 2)
                pnl_pct = round((pnl / cost_val) * 100, 2) if cost_val > 0 else 0.0

                holdings_val += cur_val
                unrealized_pnl += pnl
                margin_used += (cost_val / 5) if pos["product"] == "MIS" else cost_val

                positions_res.append(PaperPositionResponse(
                    symbol=sym,
                    product=pos["product"],
                    qty=qty,
                    avg_price=buy_price,
                    ltp=ltp,
                    current_value=cur_val,
                    pnl=pnl,
                    pnl_pct=pnl_pct
                ))

            total_value = round(self.cash + margin_used + unrealized_pnl, 2)

            return PaperPortfolioResponse(
                ledger_epoch=self.ledger_epoch,
                total_portfolio_value=total_value,
                cash_balance=round(self.cash, 2),
                margin_used=round(margin_used, 2),
                unrealized_pnl=round(unrealized_pnl, 2),
                realized_pnl=round(self.realized_pnl, 2),
                total_trades_count=len(self.orders),
                positions=positions_res,
                orders=[dict(order) for order in self.orders]
            )

    def execute_order(self, req: PaperOrderRequest) -> Dict:
        sym = req.symbol.upper()
        side = req.side.upper()
        prod = req.product.upper()
        qty = req.qty
        profit: Optional[float] = None
        client_order_id = str(req.client_order_id).strip() if req.client_order_id else ""
        order_id = client_order_id or uuid.uuid4().hex
        created_at = str(req.created_at) if req.created_at else datetime.utcnow().isoformat() + "Z"

        candidate = {
            "time": datetime.utcnow().strftime("%I:%M %p"),
            "side": side,
            "symbol": sym,
            "product": prod,
            "qty": qty,
            "price": req.price,
            "status": "EXECUTED",
            "pnl": None,
        }

        with self._lock:
            existing = self._find_existing_order(order_id, candidate)
            if existing:
                return {
                    "success": True,
                    "duplicate": True,
                    "message": f"{side} {qty}x {sym} was already executed",
                }
            quote = market_ingest.get_quote(sym)
            ltp = quote.price if quote else (req.price or 1000.0)
            exec_price = req.price if (req.order_type == "LIMIT" and req.price) else ltp

            order_val = qty * exec_price
            margin_req = (order_val / 5) if prod == "MIS" else order_val
            pos_key = f"{sym}_{prod}"

            if side == "BUY":
                if self.cash < margin_req:
                    raise ValueError(
                        f"Insufficient virtual cash! Required: ₹{round(margin_req, 2)}, Available: ₹{round(self.cash, 2)}"
                    )

                self.cash -= margin_req
                if pos_key in self.positions:
                    existing = self.positions[pos_key]
                    new_qty = existing["qty"] + qty
                    existing["buy_price"] = round(
                        ((existing["buy_price"] * existing["qty"]) + (exec_price * qty)) / new_qty, 2
                    )
                    existing["qty"] = new_qty
                else:
                    self.positions[pos_key] = {
                        "symbol": sym, "product": prod, "qty": qty, "buy_price": exec_price
                    }

            elif side == "SELL":
                if pos_key not in self.positions or self.positions[pos_key]["qty"] < qty:
                    raise ValueError(
                        f"You do not hold sufficient {qty} units of {sym} ({prod}) to sell"
                    )

                existing = self.positions[pos_key]
                profit = round((exec_price - existing["buy_price"]) * qty, 2)
                margin_to_return = (
                    (existing["buy_price"] * qty / 5) if prod == "MIS" else (existing["buy_price"] * qty)
                )

                self.cash += margin_to_return + profit
                self.realized_pnl += profit

                existing["qty"] -= qty
                if existing["qty"] <= 0:
                    del self.positions[pos_key]

            else:
                raise ValueError(f"Unsupported order side: {side}")

            time_str = candidate["time"]
            self.orders.insert(0, {
                "client_order_id": order_id,
                "created_at": created_at,
                "time": time_str,
                "side": side,
                "symbol": sym,
                "product": prod,
                "qty": qty,
                "price": exec_price,
                "status": "EXECUTED",
                "pnl": round(profit, 2) if profit is not None else None
            })
            self.orders = self.orders[:200]
            self._save_state()

            return {"success": True, "message": f"{side} {qty}x {sym} executed @ ₹{exec_price:.2f}"}

    def square_off_position(
        self,
        symbol: str,
        product: str,
        client_order_id: Optional[str] = None,
        created_at: Optional[str] = None,
        price: Optional[float] = None,
    ) -> Dict:
        sym = symbol.upper().strip()
        prod = product.upper().strip()
        pos_key = f"{sym}_{prod}"
        order_id = str(client_order_id).strip() if client_order_id else uuid.uuid4().hex
        order_time = datetime.utcnow().strftime("%I:%M %p")
        order_created_at = str(created_at) if created_at else datetime.utcnow().isoformat() + "Z"

        with self._lock:
            existing = self._find_existing_order(order_id)
            if existing:
                return {
                    "success": True,
                    "duplicate": True,
                    "message": f"Square-off for {sym} was already executed",
                }
            if pos_key not in self.positions:
                raise ValueError(f"No active position found for {sym} ({prod})")

            pos = self.positions[pos_key]
            quote = market_ingest.get_quote(sym)
            replay_price = float(price) if price is not None and math.isfinite(float(price)) and float(price) > 0 else None
            ltp = replay_price or (quote.price if quote else pos["buy_price"])
            qty = pos["qty"]

            profit = (ltp - pos["buy_price"]) * qty
            margin_to_return = (
                (pos["buy_price"] * qty / 5) if prod == "MIS" else (pos["buy_price"] * qty)
            )

            self.cash += margin_to_return + profit
            self.realized_pnl += profit
            del self.positions[pos_key]

            self.orders.insert(0, {
                "client_order_id": order_id,
                "created_at": order_created_at,
                "time": order_time,
                "side": "SELL",
                "symbol": sym,
                "product": prod,
                "qty": qty,
                "price": ltp,
                "status": "SQUARED OFF",
                "pnl": round(profit, 2)
            })
            self.orders = self.orders[:200]
            self._save_state()

            return {
                "success": True,
                "pnl": round(profit, 2),
                "message": f"Squared off {sym} @ ₹{ltp:.2f} (P&L: ₹{profit:+.2f})"
            }

    def reset_account(self) -> Dict:
        with self._lock:
            self.cash = self.initial_capital
            self.realized_pnl = 0.0
            self.positions.clear()
            self.orders.clear()
            self.ledger_epoch = uuid.uuid4().hex[:12]
            self._save_state()
            return {
                "success": True,
                "message": "Paper portfolio reset to ₹10,00,000 cash balance",
                "ledger_epoch": self.ledger_epoch,
            }


paper_trading = PaperTradingEngine()
