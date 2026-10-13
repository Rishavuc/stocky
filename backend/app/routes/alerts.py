from fastapi import APIRouter, HTTPException
from typing import List
from app.services.alert_engine import alert_engine
from app.schemas.schemas import AlertCreateRequest, AlertRuleResponse

router = APIRouter(prefix="/v1/alerts", tags=["Alerts"])

@router.get("", response_model=List[AlertRuleResponse])
async def get_alerts():
    return alert_engine.get_rules()

@router.post("", response_model=AlertRuleResponse)
async def create_alert(req: AlertCreateRequest):
    return alert_engine.create_rule(req)

@router.delete("/{rule_id}")
async def delete_alert(rule_id: int):
    success = alert_engine.delete_rule(rule_id)
    if not success:
        raise HTTPException(status_code=404, detail="Alert rule not found")
    return {"success": True, "message": "Alert deleted"}

@router.get("/history")
async def get_alert_history():
    return alert_engine.events_history
