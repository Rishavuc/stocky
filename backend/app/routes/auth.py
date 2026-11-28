from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from collections import defaultdict, deque
from datetime import datetime
import json
import re
import time
import hashlib
import secrets
import threading
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from fastapi.concurrency import run_in_threadpool
from google.oauth2 import id_token as google_id_token
from google.auth.transport import requests as google_requests
from google.auth import exceptions as google_auth_exceptions

from app.config import settings, is_configured
from app.security import issue_session_token, optional_user_id, current_user_id
from app.database import get_db
from app.models.entities import User, PaperAccount, UserActivity
from app.services.activity_logger import record_activity

router = APIRouter(prefix="/v1/auth", tags=["Authentication & User Management"])

DEMO_USER_ID = "usr_demo_1001"

# ========================================================
# CRYPTOGRAPHIC PASSWORD HASHING (PBKDF2-HMAC-SHA256)
# ========================================================
# New hashes store their work factor in the salt column as "p<iters>$<hex>".
# Old rows have a bare hex salt and were made with 100k iterations; they are
# upgraded on the next successful login.
LEGACY_ITERATIONS = 100_000
PBKDF2_ITERATIONS = 310_000  # OWASP PBKDF2-SHA256 guidance, sized for Render's small CPU

def _iterations_for(salt: str) -> int:
    if salt.startswith("p") and "$" in salt:
        try:
            return int(salt[1:salt.index("$")])
        except ValueError:
            pass
    return LEGACY_ITERATIONS

def hash_password(password: str, salt: Optional[str] = None) -> tuple[str, str]:
    if not salt:
        salt = f"p{PBKDF2_ITERATIONS}${secrets.token_hex(16)}"
    hashed = hashlib.pbkdf2_hmac(
        'sha256',
        password.encode('utf-8'),
        salt.encode('utf-8'),
        _iterations_for(salt),
    ).hex()
    return hashed, salt

def verify_password(password: str, hashed_password: str, salt: str) -> bool:
    hashed, _ = hash_password(password, salt)
    return secrets.compare_digest(hashed, hashed_password)

# PBKDF2 output is hex, so this value can never match: password login always
# fails for accounts whose email ownership was proven through Google.
GOOGLE_ONLY_HASH = "!google-only"

def needs_rehash(salt: str) -> bool:
    return _iterations_for(salt) < PBKDF2_ITERATIONS

# PBKDF2 is deliberately slow; run it off the event loop so one login does
# not stall every other request.
async def hash_password_async(password: str, salt: Optional[str] = None) -> tuple[str, str]:
    return await run_in_threadpool(hash_password, password, salt)

async def verify_password_async(password: str, hashed_password: str, salt: str) -> bool:
    return await run_in_threadpool(verify_password, password, hashed_password, salt)

# Burned on unknown users so response time does not reveal which emails exist.
_DUMMY_SALT = f"p{PBKDF2_ITERATIONS}${secrets.token_hex(16)}"
_DUMMY_HASH = hash_password(secrets.token_urlsafe(16), _DUMMY_SALT)[0]

# ========================================================
# LOGIN RATE LIMITING (in-memory, per process)
# ========================================================
class SlidingWindowLimiter:
    """Allow at most `limit` hits per key within `window` seconds."""

    def __init__(self, limit: int, window: float):
        self.limit = limit
        self.window = window
        self._hits: dict[str, deque] = defaultdict(deque)
        self._lock = threading.Lock()

    def _prune(self, key: str, now: float) -> deque:
        q = self._hits[key]
        while q and now - q[0] > self.window:
            q.popleft()
        return q

    def blocked(self, key: str) -> bool:
        with self._lock:
            now = time.monotonic()
            q = self._prune(key, now)
            if not q:
                self._hits.pop(key, None)
            return len(q) >= self.limit

    def hit(self, key: str) -> None:
        with self._lock:
            now = time.monotonic()
            self._prune(key, now).append(now)
            if len(self._hits) > 50_000:
                self._sweep(now)

    def _sweep(self, now: float) -> None:
        # Bound memory under a flood without wiping live lockouts (a blanket
        # clear() would reset every account's failure counter).
        for k in [k for k, q in self._hits.items() if not q or now - q[-1] > self.window]:
            del self._hits[k]
        if len(self._hits) > 50_000:
            oldest = sorted(self._hits, key=lambda k: self._hits[k][-1])
            for k in oldest[: len(oldest) // 2]:
                del self._hits[k]

    def reset(self, key: str) -> None:
        with self._lock:
            self._hits.pop(key, None)

# Failed password attempts: per IP and per account. Sign-up/Google: per IP.
_login_ip_limiter = SlidingWindowLimiter(limit=20, window=15 * 60)
# Per (account, IP): one attacker cannot lock the real owner out from
# another address. Per account (loose): backstop against spread-out guessing.
_login_account_limiter = SlidingWindowLimiter(limit=10, window=15 * 60)
_login_account_total_limiter = SlidingWindowLimiter(limit=100, window=15 * 60)
DEMO_EMAIL = "demo@investorseye.com"
_signup_ip_limiter = SlidingWindowLimiter(limit=10, window=60 * 60)
_google_ip_limiter = SlidingWindowLimiter(limit=30, window=15 * 60)
# Backstop if per-IP keys are rotated: total sign-ups per hour, all clients.
_signup_global_limiter = SlidingWindowLimiter(limit=300, window=60 * 60)

def client_ip(request: Request) -> str:
    """Best-effort client address for rate limiting.

    Behind Render's proxy the socket peer is the proxy, so read
    X-Forwarded-For. Only the RIGHTMOST entry is trusted: it is the one the
    proxy appended. Anything to its left was sent by the client and can be
    forged to dodge the limiter.
    """
    if settings.TRUST_PROXY_HEADERS:
        forwarded = request.headers.get("x-forwarded-for", "")
        last = forwarded.split(",")[-1].strip() if forwarded else ""
        if last:
            return last[:64]
    return request.client.host if request.client else "unknown"

def _too_many() -> HTTPException:
    return HTTPException(
        status_code=429,
        detail="Too many attempts. Please wait a few minutes and try again.",
        headers={"Retry-After": "900"},
    )

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
INVALID_LOGIN = "Incorrect email or password. Please try again, or click Create Account to register."

def avatar_initials(name: str) -> str:
    parts = name.split()
    initials = "".join(p[0] for p in parts[:2]).upper()
    return initials or "IE"

# ========================================================
# SCHEMAS
# ========================================================
class LoginRequest(BaseModel):
    username_or_email: str = Field(..., max_length=254)
    password: str = Field(..., max_length=256)

class RegisterRequest(BaseModel):
    name: str = Field(..., max_length=100)
    email: str = Field(..., max_length=254)
    password: str = Field(..., max_length=256)
    trading_interest: Optional[str] = Field("stocks", max_length=32)

class AuthResponse(BaseModel):
    success: bool
    access_token: str
    token_type: str = "Bearer"
    user: Dict[str, Any]

# Helper to ensure seed demo accounts exist in database
async def ensure_demo_users(db: AsyncSession):
    # The demo password is public (login.html ships it). The account can only
    # see its own paper portfolio and a redacted activity trail, and cannot
    # change broker connections.
    if not settings.DEMO_USERS_ENABLED:
        return
    demo_email = "demo@investorseye.com"
    stmt = select(User).where(func.lower(User.email) == demo_email)
    res = await db.execute(stmt)
    existing = res.scalars().first()
    
    if not existing:
        pwd_hash, salt = await hash_password_async("demo")
        demo_user = User(
            user_id=DEMO_USER_ID,
            name="Demo Trader",
            email=demo_email,
            hashed_password=pwd_hash,
            salt=salt,
            plan="Institutional Alpha",
            avatar="DT",
            trading_interest="stocks",
            virtual_balance=1000000.0,
            created_at=datetime.utcnow()
        )
        db.add(demo_user)
        paper_acc = PaperAccount(
            user_id=DEMO_USER_ID,
            initial_cash=1000000.0,
            cash=1000000.0
        )
        db.add(paper_acc)
        try:
            await db.commit()
        except Exception:
            # Two first-ever logins raced to create the demo user; one wins.
            await db.rollback()

# ========================================================
# REGISTER ENDPOINT (DATABASE STORED)
# ========================================================
@router.post("/register", response_model=AuthResponse)
async def register(req: RegisterRequest, request: Request, db: AsyncSession = Depends(get_db)):
    ip_key = client_ip(request)
    if _signup_ip_limiter.blocked(ip_key) or _signup_global_limiter.blocked("all"):
        raise _too_many()
    _signup_ip_limiter.hit(ip_key)
    _signup_global_limiter.hit("all")

    clean_email = req.email.lower().strip()
    clean_name = req.name.strip()

    if not clean_email or not clean_name:
        raise HTTPException(status_code=400, detail="Name and email are required.")

    if not _EMAIL_RE.match(clean_email):
        raise HTTPException(status_code=400, detail="Please enter a valid email address.")

    if len(req.password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters long.")

    # 1. Check if user already exists in database
    stmt = select(User).where(func.lower(User.email) == clean_email)
    res = await db.execute(stmt)
    existing_user = res.scalars().first()

    if existing_user:
        raise HTTPException(status_code=400, detail="An account with this email already exists. Please sign in.")

    # 2. Hash password securely
    hashed_pwd, salt = await hash_password_async(req.password)

    user_uid = f"usr_{secrets.token_hex(6)}"

    # 4. Insert User Profile and Virtual Trading Wallet into Database
    new_user = User(
        user_id=user_uid,
        name=clean_name,
        email=clean_email,
        hashed_password=hashed_pwd,
        salt=salt,
        plan="Pro Trader",
        avatar=avatar_initials(clean_name),
        trading_interest=req.trading_interest or "stocks",
        virtual_balance=1000000.0,
        created_at=datetime.utcnow(),
        last_login_at=datetime.utcnow()
    )
    db.add(new_user)

    # Initialize associated paper account
    paper_wallet = PaperAccount(
        user_id=user_uid,
        initial_cash=1000000.0,
        cash=1000000.0
    )
    db.add(paper_wallet)

    await db.commit()
    await db.refresh(new_user)

    session_token = issue_session_token(user_uid)
    await record_activity(
        user_id=user_uid,
        event_type="register",
        method="POST",
        path="/v1/auth/register",
        status_code=200,
        details={"email": clean_email, "plan": new_user.plan},
    )

    return {
        "success": True,
        "access_token": session_token,
        "token_type": "Bearer",
        "user": {
            "id": new_user.user_id,
            "name": new_user.name,
            "email": new_user.email,
            "plan": new_user.plan,
            "avatar": new_user.avatar,
            "virtual_balance": new_user.virtual_balance,
            "created_at": new_user.created_at.isoformat()
        }
    }

# ========================================================
# LOGIN ENDPOINT (DATABASE VERIFIED)
# ========================================================
async def find_login_user(db: AsyncSession, identifier: str) -> Optional[User]:
    """Email first, then user id, then display name only if it is unique.

    Names are not unique, so a stranger registering with your name (or your
    email as their name) must never shadow your account.
    """
    res = await db.execute(select(User).where(func.lower(User.email) == identifier))
    user = res.scalars().first()
    if user:
        return user
    res = await db.execute(select(User).where(User.user_id == identifier))
    user = res.scalars().first()
    if user:
        return user
    res = await db.execute(select(User).where(func.lower(User.name) == identifier).limit(2))
    matches = res.scalars().all()
    return matches[0] if len(matches) == 1 else None

@router.post("/login", response_model=AuthResponse)
async def login(req: LoginRequest, request: Request, db: AsyncSession = Depends(get_db)):
    await ensure_demo_users(db)
    identifier = req.username_or_email.lower().strip()

    # Handle demo shorthand
    if identifier in ["demo", "guest"]:
        identifier = "demo@investorseye.com"

    ip_key = client_ip(request)
    account_ip_key = f"{identifier}|{ip_key}"
    # The demo password is public, so locking it out would only let strangers
    # break the 1-click demo for everyone.
    limit_account = identifier != DEMO_EMAIL
    if _login_ip_limiter.blocked(ip_key) or (limit_account and (
        _login_account_limiter.blocked(account_ip_key)
        or _login_account_total_limiter.blocked(identifier)
    )):
        raise _too_many()

    # 1. Find the account
    user = await find_login_user(db, identifier)

    # 2. Verify password. Unknown users still pay for one hash, and both
    #    failures return the same message, so emails cannot be enumerated.
    if user:
        is_valid = await verify_password_async(req.password, user.hashed_password, user.salt)
    else:
        await verify_password_async(req.password, _DUMMY_HASH, _DUMMY_SALT)
        is_valid = False

    if not is_valid:
        _login_ip_limiter.hit(ip_key)
        if limit_account:
            _login_account_limiter.hit(account_ip_key)
            _login_account_total_limiter.hit(identifier)
        await record_activity(
            user_id=user.user_id if user else None,
            event_type="login_failed",
            method="POST",
            path="/v1/auth/login",
            status_code=401,
            details={"reason": "incorrect_password" if user else "user_not_found"},
        )
        raise HTTPException(status_code=401, detail=INVALID_LOGIN)

    _login_account_limiter.reset(account_ip_key)

    # 3. Upgrade legacy hashes, update last login timestamp
    if needs_rehash(user.salt):
        user.hashed_password, user.salt = await hash_password_async(req.password)
    user.last_login_at = datetime.utcnow()
    await db.commit()
    await db.refresh(user)

    session_token = issue_session_token(user.user_id)
    await record_activity(
        user_id=user.user_id,
        event_type="login_success",
        method="POST",
        path="/v1/auth/login",
        status_code=200,
        details={"last_login": user.last_login_at.isoformat()},
    )

    return {
        "success": True,
        "access_token": session_token,
        "token_type": "Bearer",
        "user": {
            "id": user.user_id,
            "name": user.name,
            "email": user.email,
            "plan": user.plan,
            "avatar": user.avatar,
            "virtual_balance": user.virtual_balance,
            "last_login": user.last_login_at.isoformat()
        }
    }

# ========================================================
# GOOGLE SIGN-IN (Google Identity Services ID token)
# ========================================================
class GoogleLoginRequest(BaseModel):
    credential: str  # the ID token (JWT) Google's button hands the browser

def google_enabled() -> bool:
    return is_configured(settings.GOOGLE_CLIENT_ID)

@router.get("/google/config")
async def google_config():
    """Public: tells login.html whether to render the Google button."""
    enabled = google_enabled()
    return {"enabled": enabled, "client_id": settings.GOOGLE_CLIENT_ID if enabled else None}

@router.post("/google", response_model=AuthResponse)
async def google_login(req: GoogleLoginRequest, request: Request, db: AsyncSession = Depends(get_db)):
    if not google_enabled():
        raise HTTPException(status_code=503, detail="Google sign-in is not configured on this server.")

    ip_key = client_ip(request)
    if _google_ip_limiter.blocked(ip_key):
        raise _too_many()
    _google_ip_limiter.hit(ip_key)

    # 1. Verify the token really came from Google, for OUR client ID, and
    #    hasn't expired. verify_oauth2_token checks signature, aud, iss, exp.
    #    It does blocking HTTP (fetches Google's certs), so run it off the loop.
    try:
        info = await run_in_threadpool(
            google_id_token.verify_oauth2_token,
            req.credential,
            google_requests.Request(),
            settings.GOOGLE_CLIENT_ID,
        )
    except ValueError:
        raise HTTPException(status_code=401, detail="Google sign-in could not be verified. Please try again.")
    except google_auth_exceptions.GoogleAuthError as exc:
        # e.g. Google's signing certs could not be fetched.
        print(f"[Google sign-in] verification unavailable: {exc}")
        raise HTTPException(status_code=503, detail="Google sign-in is temporarily unavailable. Please try again.")

    # verify_oauth2_token already checks aud and iss; pin the issuer anyway.
    if info.get("iss") not in ("accounts.google.com", "https://accounts.google.com"):
        raise HTTPException(status_code=401, detail="Google sign-in could not be verified. Please try again.")

    # 2. Only trust emails Google has verified, or anyone could claim any address.
    email = (info.get("email") or "").lower().strip()
    if not email or not info.get("email_verified"):
        raise HTTPException(status_code=401, detail="Your Google account email is not verified.")

    # 3. Find or create the user.
    res = await db.execute(select(User).where(func.lower(User.email) == email))
    user = res.scalars().first()

    if user and user.user_id == DEMO_USER_ID:
        raise HTTPException(status_code=403, detail="This Google account cannot be used here.")

    if user and user.hashed_password != GOOGLE_ONLY_HASH:
        # Register never verifies email ownership, so whoever set this password
        # may not own the address (account pre-hijacking). Google just proved
        # ownership, so the password is switched off and the account becomes
        # Google-only from now on.
        user.hashed_password = GOOGLE_ONLY_HASH

    if not user:
        name = (info.get("name") or email.split("@")[0]).strip()[:100]
        user = User(
            user_id=f"usr_{secrets.token_hex(6)}",
            name=name,
            email=email,
            hashed_password=GOOGLE_ONLY_HASH,
            salt=f"p{PBKDF2_ITERATIONS}${secrets.token_hex(16)}",
            plan="Pro Trader",
            avatar=avatar_initials(name),
            trading_interest="stocks",
            virtual_balance=1000000.0,
            created_at=datetime.utcnow(),
        )
        db.add(user)
        db.add(PaperAccount(user_id=user.user_id, initial_cash=1000000.0, cash=1000000.0))

    user.last_login_at = datetime.utcnow()
    await db.commit()
    await db.refresh(user)

    await record_activity(
        user_id=user.user_id,
        event_type="login_success",
        method="POST",
        path="/v1/auth/google",
        status_code=200,
        details={"provider": "google"},
    )

    return {
        "success": True,
        "access_token": issue_session_token(user.user_id),
        "token_type": "Bearer",
        "user": {
            "id": user.user_id,
            "name": user.name,
            "email": user.email,
            "plan": user.plan,
            "avatar": user.avatar,
            "virtual_balance": user.virtual_balance,
            "auth_provider": "google",
        },
    }

# ========================================================
# CURRENT USER ME ENDPOINT
# ========================================================
@router.get("/me")
async def get_current_user(user_uid: Optional[str] = Depends(optional_user_id), db: AsyncSession = Depends(get_db)):
    # optional_user_id has already checked the JWT signature and expiry;
    # a forged or expired token arrives here as None.
    if not user_uid:
        return {"authenticated": False, "user": None}

    res = await db.execute(select(User).where(User.user_id == user_uid))
    user = res.scalars().first()
    if not user:
        return {"authenticated": False, "user": None}

    return {
        "authenticated": True,
        "user": {
            "id": user.user_id,
            "name": user.name,
            "email": user.email,
            "plan": user.plan,
            "avatar": user.avatar,
            "virtual_balance": user.virtual_balance
        }
    }

@router.post("/logout")
async def logout(user_id: Optional[str] = Depends(optional_user_id)):
    # JWTs are stateless, so logout just records the event; the browser
    # drops its token. Forged tokens resolve to None and log nothing.
    if user_id:
        await record_activity(
            user_id=user_id,
            event_type="logout",
            method="POST",
            path="/v1/auth/logout",
            status_code=200,
        )
    return {"success": True}

# ========================================================
# USER ACTIVITY HISTORY
# ========================================================
@router.get("/activity")
async def get_user_activity(
    user_id: str = Depends(current_user_id),
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    # current_user_id verifies the signed token, so a user can only ever
    # read their own trail (IPs and user agents included).
    limit = max(1, min(limit, 200))
    # Upper bound too: SQLite/Postgres OFFSET must fit in int64, and a
    # bigger value crashed the query with OverflowError (HTTP 500).
    offset = max(0, min(offset, 1_000_000))

    stmt = (
        select(UserActivity)
        .where(UserActivity.user_id == user_id)
        .order_by(UserActivity.created_at.desc(), UserActivity.id.desc())
        .offset(offset)
        .limit(limit)
    )
    result = await db.execute(stmt)
    activities = []
    # The demo account is shared by strangers: never show one visitor
    # another visitor's IP address or browser.
    shared_account = user_id == DEMO_USER_ID

    for item in result.scalars().all():
        parsed_details = None
        if item.details:
            try:
                parsed_details = json.loads(item.details)
            except (TypeError, ValueError):
                parsed_details = None
        activities.append({
            "id": item.activity_id,
            "event_type": item.event_type,
            "method": item.method,
            "path": item.path,
            "status_code": item.status_code,
            "ip_address": None if shared_account else item.ip_address,
            "user_agent": None if shared_account else item.user_agent,
            "details": parsed_details,
            "created_at": item.created_at.isoformat() if item.created_at else None,
        })

    return {"user_id": user_id, "count": len(activities), "activities": activities}
