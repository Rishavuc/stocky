from datetime import datetime
from typing import Dict, List, Optional
from app.services.market_ingest import market_ingest
from app.schemas.schemas import PaperOrderRequest, PaperPortfolioResponse, PaperPositionResponse

class PaperTradingEngine:
    def __init__(self):
        self.initial_capital: float = 1000000.0
        self.cash: float = 909600.0
        self.realized_pnl: float = 0.0
        self.positions: Dict[str, Dict] = {
            "RELIANCE_CNC": {"symbol": "RELIANCE", "product": "CNC", "qty": 30, "buy_price": 1180.00},
            "INFY_MIS": {"symbol": "INFY", "product": "MIS", "qty": 50, "buy_price": 1100.00}
        }
        self.orders: List[Dict] = [
            {"time": "10:15 AM", "side": "BUY", "symbol": "RELIANCE", "product": "CNC", "qty": 30, "price": 1180.00, "status": "EXECUTED"},
            {"time": "11:42 AM", "side": "BUY", "symbol": "INFY", "product": "MIS", "qty": 50, "price": 1100.00, "status": "EXECUTED"},
        ]

    def get_portfolio(self) -> PaperPortfolioResponse:
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
            total_portfolio_value=total_value,
            cash_balance=round(self.cash, 2),
            margin_used=round(margin_used, 2),
            unrealized_pnl=round(unrealized_pnl, 2),
            realized_pnl=round(self.realized_pnl, 2),
            total_trades_count=len(self.orders),
            positions=positions_res
        )

    def execute_order(self, req: PaperOrderRequest) -> Dict:
        sym = req.symbol.upper()
        side = req.side.upper()
        prod = req.product.upper()
        qty = req.qty

        quote = market_ingest.get_quote(sym)
        ltp = quote.price if quote else (req.price or 1000.0)
        exec_price = req.price if (req.order_type == "LIMIT" and req.price) else ltp

        order_val = qty * exec_price
        margin_req = (order_val / 5) if prod == "MIS" else order_val
        pos_key = f"{sym}_{prod}"

        if side == "BUY":
            if self.cash < margin_req:
                raise ValueError(f"Insufficient virtual cash! Required: ₹{round(margin_req, 2)}, Available: ₹{round(self.cash, 2)}")

            self.cash -= margin_req
            if pos_key in self.positions:
                existing = self.positions[pos_key]
                new_qty = existing["qty"] + qty
                existing["buy_price"] = round(((existing["buy_price"] * existing["qty"]) + (exec_price * qty)) / new_qty, 2)
                existing["qty"] = new_qty
            else:
                self.positions[pos_key] = {"symbol": sym, "product": prod, "qty": qty, "buy_price": exec_price}

        elif side == "SELL":
            if pos_key not in self.positions or self.positions[pos_key]["qty"] < qty:
                raise ValueError(f"You do not hold sufficient {qty} units of {sym} ({prod}) to sell")

            existing = self.positions[pos_key]
            profit = (exec_price - existing["buy_price"]) * qty
            margin_to_return = (existing["buy_price"] * qty / 5) if prod == "MIS" else (existing["buy_price"] * qty)

            self.cash += margin_to_return + profit
            self.realized_pnl += profit

            existing["qty"] -= qty
            if existing["qty"] <= 0:
                del self.positions[pos_key]

        # Log order
        time_str = datetime.utcnow().strftime("%I:%M %p")
        self.orders.insert(0, {
            "time": time_str,
            "side": side,
            "symbol": sym,
            "product": prod,
            "qty": qty,
            "price": exec_price,
            "status": "EXECUTED"
        })

        return {"success": True, "message": f"{side} {qty}x {sym} executed @ ₹{exec_price:.2f}"}

    def square_off_position(self, symbol: str, product: str) -> Dict:
        pos_key = f"{symbol.upper()}_{product.upper()}"
        if pos_key not in self.positions:
            raise ValueError(f"No active position found for {symbol} ({product})")

        pos = self.positions[pos_key]
        quote = market_ingest.get_quote(symbol.upper())
        ltp = quote.price if quote else pos["buy_price"]
        qty = pos["qty"]

        profit = (ltp - pos["buy_price"]) * qty
        margin_to_return = (pos["buy_price"] * qty / 5) if product == "MIS" else (pos["buy_price"] * qty)

        self.cash += margin_to_return + profit
        self.realized_pnl += profit
        del self.positions[pos_key]

        time_str = datetime.utcnow().strftime("%I:%M %p")
        self.orders.insert(0, {
            "time": time_str,
            "side": "SELL",
            "symbol": symbol.upper(),
            "product": product.upper(),
            "qty": qty,
            "price": ltp,
            "status": "SQUARED OFF"
        })

        return {"success": True, "pnl": round(profit, 2), "message": f"Squared off {symbol} @ ₹{ltp:.2f} (P&L: ₹{profit:+.2f})"}

    def reset_account(self) -> Dict:
        self.cash = self.initial_capital
        self.realized_pnl = 0.0
        self.positions.clear()
        self.orders.clear()
        return {"success": True, "message": "Paper portfolio reset to ₹10,00,000 cash balance"}

paper_trading = PaperTradingEngine()
