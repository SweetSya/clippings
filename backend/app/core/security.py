import time
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict
import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from fastapi import HTTPException, Security, Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.config import settings

# Argon2id password hasher with specified parameters: time_cost=3, memory_cost=65536, parallelism=2
ph = PasswordHasher(
    time_cost=3,
    memory_cost=65536,
    parallelism=2,
    hash_len=32,
    salt_len=16
)

# In-memory brute force tracker: ip -> {"attempts": int, "cooldown_until": float}
_failed_attempts: Dict[str, Dict[str, float]] = {}

def hash_pin(pin: str) -> str:
    return ph.hash(pin)

def verify_pin(pin_hash: str, pin: str) -> bool:
    try:
        return ph.verify(pin_hash, pin)
    except VerifyMismatchError:
        return False
    except Exception:
        return False

def check_brute_force(ip: str):
    now = time.time()
    record = _failed_attempts.get(ip)
    if record:
        if record["cooldown_until"] > now:
            remaining = int(record["cooldown_until"] - now)
            raise HTTPException(
                status_code=429,
                detail=f"Terlalu banyak percobaan gagal. Silakan coba lagi dalam {remaining} detik."
            )
        elif now > record["cooldown_until"] and record["cooldown_until"] > 0:
            # Cooldown expired, reset
            _failed_attempts[ip] = {"attempts": 0, "cooldown_until": 0}

def record_failed_attempt(ip: str):
    now = time.time()
    record = _failed_attempts.get(ip, {"attempts": 0, "cooldown_until": 0})
    record["attempts"] += 1
    if record["attempts"] >= 5:
        record["cooldown_until"] = now + 300  # 5 minutes cooldown
    _failed_attempts[ip] = record

def reset_failed_attempts(ip: str):
    if ip in _failed_attempts:
        _failed_attempts.pop(ip, None)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(days=7)
    to_encode.update({
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "sub": "local-user",
        "type": "access"
    })
    encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET, algorithm="HS256")
    return encoded_jwt

security_bearer = HTTPBearer(auto_error=False)

async def get_current_session(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Security(security_bearer)
):
    token = None
    if credentials and credentials.credentials:
        token = credentials.credentials
    elif "token" in request.query_params:
        token = request.query_params.get("token")
    elif "access_token" in request.cookies:
        token = request.cookies.get("access_token")

    if not token:
        raise HTTPException(
            status_code=401,
            detail={"error": {"code": "UNAUTHORIZED", "message": "Token autentikasi tidak ditemukan atau tidak valid."}}
        )

    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=["HS256"])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=401,
            detail={"error": {"code": "TOKEN_EXPIRED", "message": "Sesi telah berakhir. Silakan masukkan PIN kembali."}}
        )
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=401,
            detail={"error": {"code": "INVALID_TOKEN", "message": "Token tidak valid."}}
        )

async def get_media_session(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Security(security_bearer)
):
    """
    Permissive session validator for media streaming (videos, thumbnails, audio).
    Supports Bearer header, ?token= query parameter, access_token cookie,
    and allows local requests from localhost / 127.0.0.1 for HTML5 media tags.
    """
    token = None
    if credentials and credentials.credentials:
        token = credentials.credentials
    elif "token" in request.query_params:
        token = request.query_params.get("token")
    elif "access_token" in request.cookies:
        token = request.cookies.get("access_token")

    if token:
        try:
            return jwt.decode(token, settings.JWT_SECRET, algorithms=["HS256"])
        except Exception:
            pass

    # For local media playback (HTML5 video/audio/img elements that don't send headers)
    client_host = request.client.host if request.client else "127.0.0.1"
    if client_host in ("127.0.0.1", "localhost", "::1"):
        return {"sub": "local-media-user", "type": "media"}

    raise HTTPException(
        status_code=401,
        detail={"error": {"code": "UNAUTHORIZED", "message": "Token autentikasi media tidak valid."}}
    )
