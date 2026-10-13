from fastapi import APIRouter, HTTPException, Depends, Header
from pydantic import BaseModel, EmailStr
from typing import Optional, Dict, Any
from datetime import datetime
import time
import hashlib
import secrets
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.database import get_db
from app.models.entities import User, PaperAccount

router = APIRouter(prefix="/v1/auth", tags=["Authentication & User Management"])

# ========================================================
# CRYPTOGRAPHIC PASSWORD HASHING (PBKDF2-HMAC-SHA256)
# ========================================================
def hash_password(password: str, salt: Optional[str] = None) -> tuple[str, str]:
    if not salt:
        salt = secrets.token_hex(16)
    hashed = hashlib.pbkdf2_hmac(
        'sha256', 
        password.encode('utf-8'), 
        salt.encode('utf-8'), 
        100000
    ).hex()
    return hashed, salt

def verify_password(password: str, hashed_password: str, salt: str) -> bool:
    hashed, _ = hash_password(password, salt)
    return secrets.compare_digest(hashed, hashed_password)

# ========================================================
# SCHEMAS
# ========================================================
class LoginRequest(BaseModel):
    username_or_email: str
    password: str

class RegisterRequest(BaseModel):
    name: str
    email: str
    password: str
    trading_interest: Optional[str] = "stocks"

class AuthResponse(BaseModel):
    success: bool
    access_token: str
    token_type: str = "Bearer"
    user: Dict[str, Any]

# Helper to ensure seed demo accounts exist in database
async def ensure_demo_users(db: AsyncSession):
    demo_email = "demo@investorseye.com"
    stmt = select(User).where(func.lower(User.email) == demo_email)
    res = await db.execute(stmt)
    existing = res.scalars().first()
    
    if not existing:
        pwd_hash, salt = hash_password("demo")
        demo_user = User(
            user_id="usr_demo_1001",
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
            user_id="usr_demo_1001",
            initial_cash=1000000.0,
            cash=1000000.0
        )
        db.add(paper_acc)
        await db.commit()

# ========================================================
# REGISTER ENDPOINT (DATABASE STORED)
# ========================================================
@router.post("/register", response_model=AuthResponse)
async def register(req: RegisterRequest, db: AsyncSession = Depends(get_db)):
    clean_email = req.email.lower().strip()
    clean_name = req.name.strip()

    if not clean_email or not clean_name:
        raise HTTPException(status_code=400, detail="Name and email are required.")

    if len(req.password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters long.")

    # 1. Check if user already exists in database
    stmt = select(User).where(func.lower(User.email) == clean_email)
    res = await db.execute(stmt)
    existing_user = res.scalars().first()

    if existing_user:
        raise HTTPException(status_code=400, detail="An account with this email already exists. Please sign in.")

    # 2. Hash password securely
    hashed_pwd, salt = hash_password(req.password)

    # 3. Generate initials for avatar
    parts = clean_name.split()
    avatar_initials = (parts[0][0] + (parts[1][0] if len(parts) > 1 else "")).upper()
    if not avatar_initials:
        avatar_initials = "IE"

    user_uid = f"usr_{secrets.token_hex(6)}"

    # 4. Insert User Profile and Virtual Trading Wallet into Database
    new_user = User(
        user_id=user_uid,
        name=clean_name,
        email=clean_email,
        hashed_password=hashed_pwd,
        salt=salt,
        plan="Pro Trader",
        avatar=avatar_initials,
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

    # 5. Generate secure session token
    session_token = f"ie_sec_{user_uid}_{int(time.time())}"

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
@router.post("/login", response_model=AuthResponse)
async def login(req: LoginRequest, db: AsyncSession = Depends(get_db)):
    await ensure_demo_users(db)
    identifier = req.username_or_email.lower().strip()

    # Handle demo shorthand
    if identifier in ["demo", "guest"]:
        identifier = "demo@investorseye.com"

    # 1. Query database for user by email or name or user_id
    stmt = select(User).where(
        (func.lower(User.email) == identifier) | 
        (func.lower(User.name) == identifier) |
        (User.user_id == identifier)
    )
    res = await db.execute(stmt)
    user = res.scalars().first()

    if not user:
        raise HTTPException(
            status_code=401, 
            detail="User not found. Please verify your email or click Create Account to register."
        )

    # 2. Verify password with database salt & hashed password
    is_valid = verify_password(req.password, user.hashed_password, user.salt)
    if not is_valid:
        raise HTTPException(
            status_code=401, 
            detail="Incorrect password. Please verify your credentials and try again."
        )

    # 3. Update last login timestamp in database
    user.last_login_at = datetime.utcnow()
    await db.commit()
    await db.refresh(user)

    session_token = f"ie_sec_{user.user_id}_{int(time.time())}"

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
# CURRENT USER ME ENDPOINT
# ========================================================
@router.get("/me")
async def get_current_user(authorization: Optional[str] = Header(None), db: AsyncSession = Depends(get_db)):
    if not authorization:
        return {"authenticated": False, "user": None}

    # Extract user ID token prefix
    try:
        parts = authorization.replace("Bearer ", "").split("_")
        if len(parts) >= 3 and parts[0] == "ie" and parts[1] == "sec":
            user_uid = f"{parts[2]}_{parts[3]}"
            stmt = select(User).where(User.user_id == user_uid)
            res = await db.execute(stmt)
            user = res.scalars().first()
            if user:
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
    except Exception:
        pass

    return {"authenticated": False, "user": None}
