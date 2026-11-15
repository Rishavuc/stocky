"""Durable notification outbox with leases and explicit uncertain delivery states."""

import os, json, smtplib
from email.message import EmailMessage
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
import httpx
from app import trading
from app.connections import unseal
from app.store import now, DB, Record
from sqlalchemy import select


def enqueue(db, owner, event, channel_id=None):
    for channel in trading.records(db, owner, "channel"):
        if channel_id and channel.key != channel_id:
            continue
        c = channel.data
        if not c.get("verified") or not c.get("enabled", True):
            continue
        key = event["id"] + ":" + channel.key
        if not trading.get(db, owner, "delivery", key):
            trading.put(
                db,
                owner,
                "delivery",
                key,
                {
                    "id": key,
                    "event": event,
                    "channel": channel.key,
                    "status": "pending",
                    "attempts": 0,
                    "created_at": now(),
                    "next_attempt": now(),
                },
            )


def quiet(settings, stamp=None):
    start = settings.get("quiet_start")
    end = settings.get("quiet_end")
    if start is None or end is None or start == end:
        return False
    hour = (
        (stamp or datetime.now(timezone.utc))
        .astimezone(ZoneInfo(settings.get("timezone", "Asia/Kolkata")))
        .hour
    )
    return start <= hour < end if start < end else hour >= start or hour < end


def send(provider, credentials, text):
    if provider == "telegram":
        r = httpx.post(
            "https://api.telegram.org/bot" + credentials["bot_token"] + "/sendMessage",
            json={"chat_id": credentials["chat_id"], "text": text},
            timeout=15,
        )
        r.raise_for_status()
        j = r.json()
        if not j.get("ok"):
            raise ValueError("Telegram rejected message")
        return {"provider_id": str(j["result"]["message_id"]), "status": "sent"}
    if provider == "email":
        m = EmailMessage()
        m["From"] = credentials["from"]
        m["To"] = credentials["to"]
        m["Subject"] = "InvestorsEYE alert"
        m.set_content(text)
        with smtplib.SMTP(
            credentials["host"], int(credentials.get("port", 587)), timeout=15
        ) as smtp:
            smtp.starttls()
            smtp.login(credentials["username"], credentials["password"])
            smtp.send_message(m)
        return {"status": "sent"}
    if provider == "whatsapp":
        r = httpx.post(
            "https://graph.facebook.com/"
            + credentials.get("api_version", "v27.0")
            + "/"
            + credentials["phone_number_id"]
            + "/messages",
            headers={"Authorization": "Bearer " + credentials["access_token"]},
            json={
                "messaging_product": "whatsapp",
                "to": credentials["to"],
                "type": "template",
                "template": {
                    "name": credentials["template"],
                    "language": {"code": credentials.get("language", "en_US")},
                    "components": [
                        {"type": "body", "parameters": [{"type": "text", "text": text}]}
                    ],
                },
            },
            timeout=15,
        )
        r.raise_for_status()
        return {"status": "sent", "provider_id": r.json()["messages"][0]["id"]}
    raise ValueError("Unsupported channel")


def deliver_one():
    stamp = now()
    with DB.begin() as db:
        # Expired leases are uncertain, never blindly retried after a possible successful send.
        for r in db.scalars(select(Record).where(Record.kind == "delivery")):
            if (
                r.data.get("status") == "sending"
                and r.data.get("lease_until", "") < stamp
            ):
                r.data = {
                    **r.data,
                    "status": "uncertain",
                    "error": "Delivery interrupted; check provider receipt before retrying.",
                }
        r = db.scalar(
            select(Record)
            .where(Record.kind == "delivery")
            .order_by(Record.id)
            .with_for_update(skip_locked=True)
        )
        candidates = list(
            db.scalars(
                select(Record)
                .where(Record.kind == "delivery")
                .with_for_update(skip_locked=True)
            )
        )
        r = next(
            (
                x
                for x in candidates
                if x.data.get("status") in ("pending", "retry")
                and x.data.get("next_attempt", "") <= stamp
            ),
            None,
        )
        if not r:
            return False
        channel = trading.get(db, r.owner, "channel", r.data["channel"])
        if (
            not channel
            or not channel.data.get("enabled")
            or not channel.data.get("verified")
        ):
            r.data = {**r.data, "status": "cancelled"}
            return True
        if quiet(channel.data):
            r.data = {
                **r.data,
                "next_attempt": (
                    datetime.now(timezone.utc) + timedelta(minutes=30)
                ).isoformat(),
            }
            return True
        rid = r.id
        owner = r.owner
        d = dict(r.data)
        c = dict(channel.data)
        r.data = {
            **d,
            "status": "sending",
            "attempts": d["attempts"] + 1,
            "lease_until": (
                datetime.now(timezone.utc) + timedelta(minutes=2)
            ).isoformat(),
        }
    e = d["event"]
    text = (
        e.get("message")
        or f"{e.get('symbol', 'Portfolio')} alert: observed {e.get('price', 'condition matched')} at {e.get('observed_at', now())}. Educational information; virtual trading only."
    )
    try:
        result = send(c["provider"], unseal(c["secret"]), text)
    except (httpx.TimeoutException, smtplib.SMTPServerDisconnected):
        result = {
            "status": "uncertain",
            "error": "Provider response was lost. Check receipt before explicitly retrying.",
        }
    except httpx.ConnectError:
        result = {
            "status": "retry" if d["attempts"] < 3 else "failed",
            "error": "Connection failed before provider acceptance",
            "next_attempt": (
                datetime.now(timezone.utc) + timedelta(seconds=30 * 2 ** d["attempts"])
            ).isoformat(),
        }
    except (httpx.HTTPError, smtplib.SMTPException, KeyError, ValueError):
        result = {
            "status": "failed",
            "error": "Provider rejected delivery or channel configuration is incomplete.",
        }
    with DB.begin() as db:
        r = db.get(Record, rid)
        if r:
            r.data = {**r.data, **result, "updated_at": now()}
    return True
