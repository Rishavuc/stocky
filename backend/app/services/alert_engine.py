from datetime import datetime
from typing import List, Dict, Any, Optional
from app.services.market_ingest import market_ingest
from app.schemas.schemas import AlertCreateRequest, AlertRuleResponse

class AlertEngineService:
    def __init__(self):
        self.rules: List[Dict] = [
            {"id": 1, "symbol": "RELIANCE", "condition_type": "PRICE_CROSSES_ABOVE", "target_value": 3000.0, "channels": "telegram,email", "active": True, "created_at": datetime.utcnow()},
            {"id": 2, "symbol": "NIFTY 50", "condition_type": "PCR_ABOVE", "target_value": 1.35, "channels": "telegram", "active": True, "created_at": datetime.utcnow()},
            {"id": 3, "symbol": "TCS", "condition_type": "PRICE_CROSSES_BELOW", "target_value": 3850.0, "channels": "email", "active": True, "created_at": datetime.utcnow()}
        ]
        self.events_history: List[Dict] = [
            {"id": 1, "symbol": "RELIANCE", "message": "RELIANCE crossed above ₹2,880.00 threshold", "channel": "telegram", "time": "Yesterday, 02:45 PM", "status": "DELIVERED"},
            {"id": 2, "symbol": "BTCINR", "message": "Bitcoin 24h volume surged +18%", "channel": "email", "time": "Today, 09:12 AM", "status": "DELIVERED"}
        ]

    def get_rules(self) -> List[AlertRuleResponse]:
        return [
            AlertRuleResponse(
                id=r["id"],
                symbol=r["symbol"],
                condition_type=r["condition_type"],
                target_value=r["target_value"],
                channels=r["channels"],
                active=r["active"],
                created_at=r["created_at"]
            )
            for r in self.rules
        ]

    def create_rule(self, req: AlertCreateRequest) -> AlertRuleResponse:
        new_id = len(self.rules) + 1
        new_rule = {
            "id": new_id,
            "symbol": req.symbol.upper(),
            "condition_type": req.condition_type,
            "target_value": req.target_value,
            "channels": req.channels,
            "active": True,
            "created_at": datetime.utcnow()
        }
        self.rules.append(new_rule)
        return AlertRuleResponse(**new_rule)

    def delete_rule(self, rule_id: int) -> bool:
        idx = next((i for i, r in enumerate(self.rules) if r["id"] == rule_id), None)
        if idx is not None:
            self.rules.pop(idx)
            return True
        return False

    def evaluate_ticks(self) -> List[Dict]:
        """Check all rules against live prices"""
        fired = []
        for r in self.rules:
            if not r["active"]:
                continue
            quote = market_ingest.get_quote(r["symbol"])
            if not quote:
                continue

            # Simple evaluation
            if r["condition_type"] == "PRICE_CROSSES_ABOVE" and quote.price >= r["target_value"]:
                msg = f"ALERT: {r['symbol']} price reached ₹{quote.price:.2f} (Target was ₹{r['target_value']:.2f})"
                event = {"symbol": r["symbol"], "message": msg, "channels": r["channels"]}
                fired.append(event)
                self.events_history.insert(0, {
                    "id": len(self.events_history) + 1,
                    "symbol": r["symbol"],
                    "message": msg,
                    "channel": r["channels"],
                    "time": "Just now",
                    "status": "DELIVERED"
                })
        return fired

alert_engine = AlertEngineService()
