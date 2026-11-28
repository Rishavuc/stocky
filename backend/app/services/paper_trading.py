import asyncio
import itertools
import json
import weakref
from datetime import datetime
from typing import Callable, Dict, List, Optional, TypeVar

from fastapi.concurrency import run_in_threadpool
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.market_ingest import market_ingest, CRYPTO_MAP, USD_INR_RATE
from app.services.universe import INDIAN_STOCKS_MAP
from app.schemas.schemas import PaperOrderRequest, PaperPortfolioResponse, PaperPositionResponse
from app.models.entities import PaperBook

T = TypeVar("T")

MIS_LEVERAGE = 5
QTY_EPSILON = 1e-9  # treat float dust left after selling crypto as zero
MAX_PENDING_ORDERS = 50  # keeps each saved book small


def _money(x: float) -> float:
    """Cash and P&L are INR: keep them at whole paise so float drift never
    piles up across thousands of fills."""
    return round(float(x) + 0.0, 2)


class BookConflict(Exception):
    """Another request saved this user's book first; caller should retry."""


def _usd_inr() -> float:
    """Live USD/INR (ECB feed, cached 30 min), else the fixed fallback."""
    try:
        rate = market_ingest.get_usd_inr_rate()
        if rate and rate > 0:
            return float(rate)
    except Exception:
        pass
    return USD_INR_RATE


def _fx(symbol: str) -> float:
    """Multiplier from the instrument's quote currency to INR (cash is INR)."""
    return _usd_inr() if symbol.endswith("USDT") else 1.0


def _ccy(symbol: str) -> str:
    return "$" if symbol.endswith("USDT") else "₹"


def _fmt_qty(qty: float) -> str:
    return str(int(qty)) if float(qty).is_integer() else f"{qty:.8f}".rstrip("0")


class PaperTradingEngine:
    def __init__(self):
        self.initial_capital: float = 1000000.0
        self.cash: float = self.initial_capital
        self.realized_pnl: float = 0.0
        self.positions: Dict[str, Dict] = {}
        self.orders: List[Dict] = []
        self.pending_orders: List[Dict] = []
        self._ids = itertools.count(1)

    # ----------------------------------------------------------------
    # Persistence: the whole book round-trips through a plain dict
    # ----------------------------------------------------------------
    def to_state(self) -> Dict:
        next_id = next(self._ids)
        self._ids = itertools.count(next_id)  # peeking consumed one id; put it back
        return {
            "version": 1,
            "cash": self.cash,
            "realized_pnl": self.realized_pnl,
            "positions": self.positions,
            "orders": self.orders[:200],  # keep the saved history bounded
            "pending_orders": self.pending_orders,
            "next_id": next_id,
        }

    @classmethod
    def from_state(cls, state: Optional[Dict]) -> "PaperTradingEngine":
        engine = cls()
        if state:
            engine.cash = _money(state.get("cash", engine.initial_capital))
            engine.realized_pnl = _money(state.get("realized_pnl", 0.0))
            engine.positions = dict(state.get("positions", {}))
            engine.orders = list(state.get("orders", []))
            engine.pending_orders = list(state.get("pending_orders", []))
            engine._ids = itertools.count(int(state.get("next_id", 1)))
        return engine

    # ----------------------------------------------------------------
    # Guards
    # ----------------------------------------------------------------
    @staticmethod
    def _cost_inr(pos: Dict) -> float:
        # Books saved before cost_inr existed: rebuild it at today's FX.
        if "cost_inr" in pos:
            return float(pos["cost_inr"])
        return _money(pos["buy_price"] * pos["qty"] * _fx(pos["symbol"]))

    @staticmethod
    def _is_crypto(symbol: str) -> bool:
        return symbol in CRYPTO_MAP

    def _validate(self, req: PaperOrderRequest) -> None:
        sym = req.symbol
        if sym not in INDIAN_STOCKS_MAP and not self._is_crypto(sym):
            raise ValueError(f"{sym} is not a tradable instrument. Pick a listed NSE stock or crypto pair.")
        if not self._is_crypto(sym) and not float(req.qty).is_integer():
            raise ValueError("Stock quantity must be a whole number of shares.")
        if self._is_crypto(sym) and req.product == "MIS":
            raise ValueError("Intraday (MIS) is only available for NSE stocks. Use Delivery (CNC) for crypto.")

    @staticmethod
    def _live_price(symbol: str) -> float:
        quote = market_ingest.get_quote(symbol)
        if not quote or quote.is_synthetic or not quote.price or quote.price <= 0:
            raise ValueError(f"No verified live price for {symbol} right now. Please try again shortly.")
        return float(quote.price)

    # ----------------------------------------------------------------
    # Core fill: the only place cash and positions change
    # ----------------------------------------------------------------
    def _fill(self, sym: str, side: str, prod: str, qty: float, price: float,
              status: str = "EXECUTED", order_type: str = "MARKET") -> Optional[float]:
        fx = _fx(sym)
        pos_key = f"{sym}_{prod}"
        profit: Optional[float] = None

        if side == "BUY":
            value_inr = _money(qty * price * fx)
            margin_req = _money(value_inr / MIS_LEVERAGE) if prod == "MIS" else value_inr
            if self.cash < margin_req:
                raise ValueError(
                    f"Insufficient virtual cash! Required: ₹{margin_req:,.2f}, Available: ₹{self.cash:,.2f}"
                )
            self.cash = _money(self.cash - margin_req)
            existing = self.positions.get(pos_key)
            if existing:
                old_cost = self._cost_inr(existing)
                new_qty = round(existing["qty"] + qty, 8)
                existing["buy_price"] = round(
                    (existing["buy_price"] * existing["qty"] + price * qty) / new_qty, 8
                )
                existing["qty"] = new_qty
                existing["cost_inr"] = _money(old_cost + value_inr)
            else:
                self.positions[pos_key] = {"symbol": sym, "product": prod, "qty": qty,
                                           "buy_price": price, "cost_inr": value_inr}
        else:  # SELL
            existing = self.positions.get(pos_key)
            if not existing or existing["qty"] + QTY_EPSILON < qty:
                raise ValueError(f"You do not hold {_fmt_qty(qty)} units of {sym} ({prod}) to sell.")
            qty = min(qty, existing["qty"])  # never sell the epsilon we tolerated
            held_cost = self._cost_inr(existing)
            # Cost basis in INR at the FX rate paid, so a crypto sale's P&L
            # matches the cash that actually comes back.
            cost_portion = _money(held_cost * qty / existing["qty"])
            proceeds_inr = _money(qty * price * fx)
            profit = _money(proceeds_inr - cost_portion)
            margin_to_return = _money(cost_portion / MIS_LEVERAGE) if prod == "MIS" else cost_portion
            self.cash = _money(self.cash + margin_to_return + profit)
            self.realized_pnl = _money(self.realized_pnl + profit)
            existing["qty"] = round(existing["qty"] - qty, 8)
            existing["cost_inr"] = _money(held_cost - cost_portion)
            if existing["qty"] <= QTY_EPSILON:
                del self.positions[pos_key]

        self.orders.insert(0, {
            "id": next(self._ids),
            "time": datetime.utcnow().strftime("%I:%M %p"),
            "side": side,
            "symbol": sym,
            "product": prod,
            "order_type": order_type,
            "qty": qty,
            "price": price,
            "status": status,
            "pnl": profit,
        })
        return profit

    # ----------------------------------------------------------------
    # Pending LIMIT orders
    # ----------------------------------------------------------------
    @staticmethod
    def _limit_reached(side: str, ltp: float, limit: float) -> bool:
        # BUY limit: fill at or below your price. SELL limit: at or above it.
        return ltp <= limit if side == "BUY" else ltp >= limit

    def _process_pending(self) -> None:
        still_pending: List[Dict] = []
        for order in self.pending_orders:
            try:
                ltp = self._live_price(order["symbol"])
            except ValueError:
                still_pending.append(order)  # no price yet, keep waiting
                continue
            if not self._limit_reached(order["side"], ltp, order["price"]):
                still_pending.append(order)
                continue
            try:
                self._fill(order["symbol"], order["side"], order["product"], order["qty"],
                           order["price"], status="EXECUTED", order_type="LIMIT")
            except ValueError as e:
                self.orders.insert(0, {**order, "status": "REJECTED", "reason": str(e), "pnl": None,
                                       "time": datetime.utcnow().strftime("%I:%M %p")})
        self.pending_orders = still_pending

    # ----------------------------------------------------------------
    # Public API (called by routes/paper_trading.py)
    # ----------------------------------------------------------------
    def get_portfolio(self) -> PaperPortfolioResponse:
        self._process_pending()
        positions_res: List[PaperPositionResponse] = []
        unrealized_pnl = 0.0
        margin_used = 0.0

        for pos in self.positions.values():
            sym, qty, buy_price = pos["symbol"], pos["qty"], pos["buy_price"]
            fx = _fx(sym)
            quote = market_ingest.get_quote(sym)
            ltp = quote.price if quote and not quote.is_synthetic else buy_price

            cost_inr = self._cost_inr(pos)
            value_inr = ltp * qty * fx
            pnl = value_inr - cost_inr

            unrealized_pnl += pnl
            margin_used += cost_inr / MIS_LEVERAGE if pos["product"] == "MIS" else cost_inr

            positions_res.append(PaperPositionResponse(
                symbol=sym,
                product=pos["product"],
                qty=qty,
                avg_price=buy_price,
                ltp=ltp,
                current_value=round(value_inr, 2),
                pnl=round(pnl, 2),
                pnl_pct=round(pnl / cost_inr * 100, 2) if cost_inr > 0 else 0.0,
            ))

        return PaperPortfolioResponse(
            total_portfolio_value=round(self.cash + margin_used + unrealized_pnl, 2),
            cash_balance=round(self.cash, 2),
            margin_used=round(margin_used, 2),
            unrealized_pnl=round(unrealized_pnl, 2),
            realized_pnl=round(self.realized_pnl, 2),
            total_trades_count=len(self.orders),
            positions=positions_res,
            orders=[dict(o) for o in self.orders],
            pending_orders=[dict(o) for o in self.pending_orders],
            usd_inr_rate=_usd_inr(),
        )

    def execute_order(self, req: PaperOrderRequest) -> Dict:
        self._process_pending()
        self._validate(req)
        sym, side, prod, qty = req.symbol, req.side, req.product, req.qty
        ltp = self._live_price(sym)
        cur = _ccy(sym)

        if req.order_type == "MARKET" or self._limit_reached(side, ltp, req.price):
            # A LIMIT that is already marketable fills now at the live price,
            # which is equal to or better than the limit.
            profit = self._fill(sym, side, prod, qty, ltp, order_type=req.order_type)
            return {
                "success": True,
                "status": "EXECUTED",
                "price": ltp,
                "pnl": profit,
                "message": f"{side} {_fmt_qty(qty)}x {sym} executed @ {cur}{ltp:,.2f}",
            }

        # Resting LIMIT order: check it could fill today, then park it.
        if len(self.pending_orders) >= MAX_PENDING_ORDERS:
            raise ValueError(f"You already have {MAX_PENDING_ORDERS} pending orders. Cancel some first.")
        if side == "SELL":
            held = self.positions.get(f"{sym}_{prod}", {}).get("qty", 0)
            if held + QTY_EPSILON < qty:
                raise ValueError(f"You do not hold {_fmt_qty(qty)} units of {sym} ({prod}) to sell.")
        else:
            value_inr = qty * req.price * _fx(sym)
            need = value_inr / MIS_LEVERAGE if prod == "MIS" else value_inr
            if self.cash < need:
                raise ValueError(f"Insufficient virtual cash! Required: ₹{need:,.2f}, Available: ₹{self.cash:,.2f}")

        order = {
            "id": next(self._ids),
            "time": datetime.utcnow().strftime("%I:%M %p"),
            "side": side,
            "symbol": sym,
            "product": prod,
            "order_type": "LIMIT",
            "qty": qty,
            "price": req.price,
            "status": "PENDING",
        }
        self.pending_orders.append(order)
        return {
            "success": True,
            "status": "PENDING",
            "order_id": order["id"],
            "message": (f"LIMIT {side} {_fmt_qty(qty)}x {sym} placed @ {cur}{req.price:,.2f}. "
                        f"It fills when the price reaches your limit (now {cur}{ltp:,.2f})."),
        }

    def cancel_order(self, order_id: int) -> Dict:
        for order in self.pending_orders:
            if order["id"] == order_id:
                self.pending_orders.remove(order)
                self.orders.insert(0, {**order, "status": "CANCELLED", "pnl": None,
                                       "time": datetime.utcnow().strftime("%I:%M %p")})
                return {"success": True, "message": f"Cancelled LIMIT {order['side']} {order['symbol']}"}
        raise ValueError(f"No pending order with id {order_id}")

    def square_off_position(self, symbol: str, product: str) -> Dict:
        sym, prod = symbol.upper().strip(), product.upper().strip()
        pos = self.positions.get(f"{sym}_{prod}")
        if not pos:
            raise ValueError(f"No active position found for {sym} ({prod})")
        ltp = self._live_price(sym)
        profit = self._fill(sym, "SELL", prod, pos["qty"], ltp, status="SQUARED OFF")
        return {"success": True, "pnl": profit,
                "message": f"Squared off {sym} @ {_ccy(sym)}{ltp:,.2f} (P&L: ₹{profit:+,.2f})"}

    def reset_account(self) -> Dict:
        self.cash = self.initial_capital
        self.realized_pnl = 0.0
        self.positions.clear()
        self.orders.clear()
        self.pending_orders.clear()
        return {"success": True, "message": "Paper portfolio reset to ₹10,00,000 cash balance"}



# --------------------------------------------------------------------
# Per-user books: load from the DB, run one operation, save it back.
# --------------------------------------------------------------------
# Weak values: a user's lock disappears once no request holds it, so the
# map can't grow forever with every user who ever traded.
_user_locks: "weakref.WeakValueDictionary[str, asyncio.Lock]" = weakref.WeakValueDictionary()

SAVE_ATTEMPTS = 3


def _lock_for(user_id: str) -> asyncio.Lock:
    # One lock per user so two quick clicks can't both read the old cash
    # and overwrite each other's trade (a lost update).
    lock = _user_locks.get(user_id)
    if lock is None:
        lock = asyncio.Lock()
        _user_locks[user_id] = lock
    return lock


async def _run_once(db: AsyncSession, user_id: str, operation: Callable[[PaperTradingEngine], T],
                    save: bool) -> T:
    res = await db.execute(select(PaperBook).where(PaperBook.user_id == user_id))
    row = res.scalars().first()
    old_state = row.state if row else None
    engine = PaperTradingEngine.from_state(json.loads(old_state) if old_state else None)

    # Engine methods fetch quotes over the network (blocking), so keep
    # them off the event loop.
    result = await run_in_threadpool(operation, engine)

    if not save:
        await db.rollback()  # end the read transaction
        return result

    new_state = json.dumps(engine.to_state())
    if new_state == old_state:
        await db.rollback()
        return result
    try:
        if row is None:
            db.add(PaperBook(user_id=user_id, state=new_state))
            await db.flush()  # unique user_id: a parallel first save fails here
        else:
            # Compare-and-swap on the state we read. The asyncio lock only
            # covers one process; this also stops a second worker (or a
            # restart overlap) from silently overwriting a trade.
            upd = await db.execute(
                update(PaperBook)
                .where(PaperBook.user_id == user_id, PaperBook.state == old_state)
                .values(state=new_state, updated_at=datetime.utcnow())
                .execution_options(synchronize_session=False)
            )
            if upd.rowcount != 1:
                raise BookConflict()
        await db.commit()
    except (IntegrityError, BookConflict):
        await db.rollback()
        raise BookConflict()
    except Exception:
        await db.rollback()
        raise
    return result


async def run_on_book(db: AsyncSession, user_id: str, operation: Callable[[PaperTradingEngine], T],
                      save: bool = True) -> T:
    async with _lock_for(user_id):
        for attempt in range(SAVE_ATTEMPTS):
            try:
                return await _run_once(db, user_id, operation, save)
            except BookConflict:
                if attempt == SAVE_ATTEMPTS - 1:
                    raise
                db.expunge_all()  # re-read the fresh row next time
            except Exception:
                await db.rollback()
                raise
