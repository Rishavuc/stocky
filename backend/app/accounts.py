"""Email verification and account recovery with hashed expiring one-use tokens."""

import os, secrets, hashlib
from datetime import datetime, timezone, timedelta
from pydantic import BaseModel, Field
from fastapi import Depends, HTTPException
from sqlalchemy import select, delete
from app.store import User, Session, now
from app import trading, notifications


class EmailRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)


class TokenRequest(BaseModel):
    token: str = Field(min_length=20, max_length=200)


class Reset(TokenRequest):
    password: str = Field(min_length=10, max_length=256)


def mail(recipient, text):
    required = [
        "AUTH_SMTP_HOST",
        "AUTH_SMTP_USER",
        "AUTH_SMTP_PASSWORD",
        "AUTH_SMTP_FROM",
    ]
    if not all(os.getenv(k) for k in required):
        raise HTTPException(
            503,
            "Account email delivery is not configured. Ask the workspace operator to configure SMTP; existing sign-in remains available.",
        )
    return notifications.send(
        "email",
        {
            "host": os.environ["AUTH_SMTP_HOST"],
            "port": os.getenv("AUTH_SMTP_PORT", "587"),
            "username": os.environ["AUTH_SMTP_USER"],
            "password": os.environ["AUTH_SMTP_PASSWORD"],
            "from": os.environ["AUTH_SMTP_FROM"],
            "to": recipient,
        },
        text,
    )


def issue(db, owner, kind):
    token = secrets.token_urlsafe(32)
    key = hashlib.sha256(token.encode()).hexdigest()
    trading.put(
        db,
        owner,
        kind,
        key,
        {
            "expires": (datetime.now(timezone.utc) + timedelta(minutes=20)).isoformat(),
            "used": False,
        },
    )
    return token


def install(app):
    from app.main import current, database, hash_password

    dep = Depends(database, scope="function")

    @app.get("/v1/auth/account")
    def state(u=Depends(current), db=dep):
        r = trading.get(db, u.id, "account_meta", "profile")
        return {
            "email": u.email,
            "verified": bool(r and r.data.get("email_verified")),
            "recovery_delivery_configured": bool(os.getenv("AUTH_SMTP_HOST")),
        }

    @app.post("/v1/auth/request-verification")
    def request_verification(u=Depends(current), db=dep):
        token = issue(db, u.id, "email_verification")
        mail(
            u.email,
            "InvestorsEYE email verification token (expires in 20 minutes): " + token,
        )
        return {"status": "sent_to_provider"}

    @app.post("/v1/auth/verify-email")
    def verify(req: TokenRequest, u=Depends(current), db=dep):
        r = trading.get(
            db,
            u.id,
            "email_verification",
            hashlib.sha256(req.token.encode()).hexdigest(),
        )
        if not r or r.data["used"] or r.data["expires"] < now():
            raise HTTPException(422, "Verification token invalid or expired")
        r.data = {**r.data, "used": True}
        trading.put(db, u.id, "account_meta", "profile", {"email_verified": True})
        return {"verified": True}

    @app.post("/v1/auth/request-recovery")
    def recovery(req: EmailRequest, db=dep):
        # Generic response prevents revealing whether an email is registered.
        user = db.scalar(select(User).where(User.email == req.email.lower().strip()))
        if user:
            existing = trading.get(db, user.id, "recovery_limit", "window")
            if existing and existing.data["until"] > now():
                return {
                    "status": "accepted",
                    "message": "If eligible, a recovery message will be sent.",
                }
            trading.put(
                db,
                user.id,
                "recovery_limit",
                "window",
                {
                    "until": (
                        datetime.now(timezone.utc) + timedelta(minutes=5)
                    ).isoformat()
                },
            )
            token = issue(db, user.id, "password_recovery")
            try:
                mail(
                    user.email,
                    "InvestorsEYE password recovery token (expires in 20 minutes): "
                    + token,
                )
            except Exception:
                pass
        return {
            "status": "accepted",
            "message": "If eligible and account email delivery is configured, a recovery message will be sent.",
        }

    @app.post("/v1/auth/reset-password")
    def reset(req: Reset, db=dep):
        from app.store import Record

        key = hashlib.sha256(req.token.encode()).hexdigest()
        r = db.scalar(
            select(Record)
            .where(Record.kind == "password_recovery", Record.key == key)
            .with_for_update()
        )
        if not r or r.data["used"] or r.data["expires"] < now():
            raise HTTPException(422, "Recovery token invalid or expired")
        u = db.scalar(select(User).where(User.id == r.owner).with_for_update())
        u.password = hash_password(req.password)
        r.data = {**r.data, "used": True}
        db.execute(delete(Session).where(Session.owner == u.id))
        return {
            "reset": True,
            "message": "Password changed; sign in again on every device.",
        }
