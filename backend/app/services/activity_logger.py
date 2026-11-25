import json
import uuid
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import delete, func, select

from app.database import AsyncSessionLocal
from app.models.entities import UserActivity
from app.security import decode_session_token


MAX_ACTIVITIES_PER_USER = 5000
SENSITIVE_KEY_PARTS = (
    "password", "passwd", "secret", "token", "authorization", "api_key", "apikey"
)


def resolve_user_id_from_header(authorization: Optional[str]) -> Optional[str]:
    """User id from a verified, signed session token, else None.

    Must verify the signature: an unverified id would let anyone write
    audit entries in another user's name.
    """
    if not authorization:
        return None
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        return None
    return decode_session_token(token.strip())


def sanitize_details(value: Any) -> Any:
    """Remove secrets before anything is written to the activity table."""
    if isinstance(value, dict):
        clean = {}
        for key, item in value.items():
            lowered = str(key).lower()
            if any(part in lowered for part in SENSITIVE_KEY_PARTS):
                continue
            clean[str(key)] = sanitize_details(item)
        return clean
    if isinstance(value, (list, tuple)):
        return [sanitize_details(item) for item in value]
    return value


async def record_activity(
    *,
    user_id: Optional[str],
    event_type: str,
    method: Optional[str] = None,
    path: Optional[str] = None,
    status_code: Optional[int] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    details: Optional[Any] = None,
) -> None:
    """Persist one audit event. Failures never break the user request."""
    try:
        stored_details = None
        if details is not None:
            stored_details = json.dumps(sanitize_details(details), default=str)

        async with AsyncSessionLocal() as db:
            db.add(UserActivity(
                activity_id=uuid.uuid4().hex,
                user_id=user_id,
                event_type=event_type,
                method=method,
                path=path,
                status_code=status_code,
                ip_address=ip_address,
                user_agent=(user_agent or "")[:500] or None,
                details=stored_details,
                created_at=datetime.utcnow(),
            ))

            if user_id:
                count = await db.scalar(
                    select(func.count(UserActivity.id)).where(UserActivity.user_id == user_id)
                )
                if count and count > MAX_ACTIVITIES_PER_USER:
                    stale_ids = (await db.execute(
                        select(UserActivity.id)
                        .where(UserActivity.user_id == user_id)
                        .order_by(UserActivity.created_at.asc())
                        .limit(int(count) - MAX_ACTIVITIES_PER_USER)
                    )).scalars().all()
                    if stale_ids:
                        await db.execute(
                            delete(UserActivity).where(UserActivity.id.in_(stale_ids))
                        )

            await db.commit()
    except Exception as exc:
        print(f"[Activity Logger] Could not record activity: {exc}")
