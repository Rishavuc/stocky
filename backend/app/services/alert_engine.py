import itertools
import logging
from collections import deque
from datetime import datetime
from typing import Deque, Dict, List

from app.services.market_ingest import market_ingest
from app.schemas.schemas import AlertCreateRequest, AlertRuleResponse

log = logging.getLogger(__name__)

MAX_RULES_PER_USER = 50
MAX_EVENTS_PER_USER = 100


class AlertEngineService:
    """In-memory alert rules, kept separately for each signed-in user.

    Every public method takes the caller's user_id, so one user can never
    list, fire or delete another user's rules. State lives in process
    memory, so it resets when the server restarts.
    """

    def __init__(self):
        self._rules: Dict[str, List[Dict]] = {}
        self._events: Dict[str, Deque[Dict]] = {}
        self._rule_ids = itertools.count(1)
        self._event_ids = itertools.count(1)

    def _user_rules(self, user_id: str) -> List[Dict]:
        return self._rules.setdefault(user_id, [])

    def _user_events(self, user_id: str) -> Deque[Dict]:
        # deque(maxlen) drops the oldest event, so history can't grow forever.
        return self._events.setdefault(user_id, deque(maxlen=MAX_EVENTS_PER_USER))

    def get_rules(self, user_id: str) -> List[AlertRuleResponse]:
        return [
            AlertRuleResponse(**{k: r[k] for k in AlertRuleResponse.model_fields})
            for r in self._user_rules(user_id)
        ]

    def get_history(self, user_id: str) -> List[Dict]:
        return list(self._user_events(user_id))

    def create_rule(self, user_id: str, req: AlertCreateRequest) -> AlertRuleResponse:
        rules = self._user_rules(user_id)
        if len(rules) >= MAX_RULES_PER_USER:
            raise ValueError(f"You can have at most {MAX_RULES_PER_USER} alerts. Delete one first.")
        new_rule = {
            # Global counter: ids never repeat, even after deletes.
            "id": next(self._rule_ids),
            "symbol": req.symbol.upper(),
            "condition_type": req.condition_type,
            "target_value": req.target_value,
            "channels": req.channels,
            "active": True,
            "created_at": datetime.utcnow(),
        }
        rules.append(new_rule)
        return AlertRuleResponse(**new_rule)

    def delete_rule(self, user_id: str, rule_id: int) -> bool:
        rules = self._user_rules(user_id)
        idx = next((i for i, r in enumerate(rules) if r["id"] == rule_id), None)
        if idx is not None:
            rules.pop(idx)
            return True
        return False

    @staticmethod
    def _triggered(rule: Dict, price: float) -> bool:
        if rule["condition_type"] == "PRICE_CROSSES_ABOVE":
            return price >= rule["target_value"]
        if rule["condition_type"] == "PRICE_CROSSES_BELOW":
            return price <= rule["target_value"]
        return False  # RSI / PCR rules are not evaluated yet

    def evaluate_ticks(self) -> List[Dict]:
        """Check every active rule against live prices. Safe to call from a
        background loop: one bad quote or rule is logged and skipped."""
        fired: List[Dict] = []
        for user_id, rules in list(self._rules.items()):
            for r in list(rules):
                if not r["active"]:
                    continue
                try:
                    quote = market_ingest.get_quote(r["symbol"])
                    if not quote or quote.is_synthetic or not quote.price:
                        continue
                    if not self._triggered(r, quote.price):
                        continue
                    direction = "above" if r["condition_type"] == "PRICE_CROSSES_ABOVE" else "below"
                    msg = (f"ALERT: {r['symbol']} price is {direction} target: ₹{quote.price:,.2f} "
                           f"(target ₹{r['target_value']:,.2f})")
                    # One-shot: otherwise it would fire again on every tick.
                    r["active"] = False
                    event = {"symbol": r["symbol"], "message": msg, "channels": r["channels"],
                             "user_id": user_id}
                    fired.append(event)
                    self._user_events(user_id).appendleft({
                        "id": next(self._event_ids),
                        "rule_id": r["id"],
                        "symbol": r["symbol"],
                        "message": msg,
                        "channel": r["channels"],
                        "time": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
                        "status": "DELIVERED",
                    })
                except Exception:
                    log.exception("Alert rule %s failed to evaluate", r.get("id"))
        return fired


alert_engine = AlertEngineService()
