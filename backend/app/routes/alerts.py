from fastapi import APIRouter, Depends, HTTPException
from typing import List
from app.security import current_user_id
from app.services.alert_engine import alert_engine
from app.schemas.schemas import AlertCreateRequest, AlertRuleResponse

router = APIRouter(prefix="/v1/alerts", tags=["Alerts"])

# Alerts belong to the signed-in user: every call passes user_id down.

@router.get("", response_model=List[AlertRuleResponse])
async def get_alerts(user_id: str = Depends(current_user_id)):
    return alert_engine.get_rules(user_id)

@router.post("", response_model=AlertRuleResponse)
async def create_alert(req: AlertCreateRequest, user_id: str = Depends(current_user_id)):
    try:
        return alert_engine.create_rule(user_id, req)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.delete("/{rule_id}")
async def delete_alert(rule_id: int, user_id: str = Depends(current_user_id)):
    # Someone else's id looks exactly like a missing one: 404, no hint it exists.
    success = alert_engine.delete_rule(user_id, rule_id)
    if not success:
        raise HTTPException(status_code=404, detail="Alert rule not found")
    return {"success": True, "message": "Alert deleted"}

@router.get("/history")
async def get_alert_history(user_id: str = Depends(current_user_id)):
    return alert_engine.get_history(user_id)
