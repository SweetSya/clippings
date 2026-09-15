import secrets
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models import AuthPin
from app.schemas import (
    AuthStatusResponse,
    PinSetupRequest,
    PinLoginRequest,
    TokenResponse
)
from app.core.security import (
    hash_pin,
    verify_pin,
    create_access_token,
    check_brute_force,
    record_failed_attempt,
    reset_failed_attempts,
    get_current_session
)

router = APIRouter(prefix="/auth", tags=["Auth"])

@router.get("/status", response_model=AuthStatusResponse)
async def get_auth_status(request: Request, db: AsyncSession = Depends(get_db)):
    active_count = await db.scalar(select(func.count()).select_from(AuthPin).where(AuthPin.is_active == True))
    is_configured = (active_count is not None and active_count > 0)
    
    # Check if request has a valid session token
    has_session = False
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]
        try:
            import jwt
            from app.config import settings
            jwt.decode(token, settings.JWT_SECRET, algorithms=["HS256"])
            has_session = True
        except Exception:
            pass

    return AuthStatusResponse(
        is_configured=is_configured,
        has_session=has_session
    )

@router.post("/setup", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def setup_pin(payload: PinSetupRequest, response: Response, db: AsyncSession = Depends(get_db)):
    # 1. Check if PIN already configured
    active_count = await db.scalar(select(func.count()).select_from(AuthPin).where(AuthPin.is_active == True))
    if active_count and active_count > 0:
        raise HTTPException(
            status_code=409,
            detail={"error": {"code": "PIN_ALREADY_CONFIGURED", "message": "PIN sistem sudah pernah dikonfigurasi."}}
        )

    # 2. Hash PIN with Argon2id
    salt = secrets.token_hex(16)
    p_hash = hash_pin(payload.pin)

    new_pin = AuthPin(
        pin_hash=p_hash,
        salt=salt,
        is_active=True
    )
    db.add(new_pin)
    await db.commit()

    token = create_access_token({"sub": "local-user"})
    response.set_cookie(key="access_token", value=token, max_age=7 * 86400, httponly=False, samesite="lax", path="/")
    return TokenResponse(token=token)

@router.post("/login", response_model=TokenResponse)
async def login_pin(request: Request, payload: PinLoginRequest, response: Response, db: AsyncSession = Depends(get_db)):
    client_ip = request.client.host if request.client else "127.0.0.1"
    
    # 1. Check brute force
    check_brute_force(client_ip)

    # 2. Retrieve active PIN
    pin_record = await db.scalar(select(AuthPin).where(AuthPin.is_active == True).order_by(AuthPin.id.desc()).limit(1))
    if not pin_record:
        raise HTTPException(
            status_code=400,
            detail={"error": {"code": "PIN_NOT_SET", "message": "PIN belum dikonfigurasi. Silakan lakukan setup terlebih dahulu."}}
        )

    # 3. Verify PIN
    if not verify_pin(pin_record.pin_hash, payload.pin):
        record_failed_attempt(client_ip)
        raise HTTPException(
            status_code=401,
            detail={"error": {"code": "INVALID_PIN", "message": "PIN yang Anda masukkan salah."}}
        )

    reset_failed_attempts(client_ip)
    token = create_access_token({"sub": "local-user"})
    response.set_cookie(key="access_token", value=token, max_age=7 * 86400, httponly=False, samesite="lax", path="/")
    return TokenResponse(token=token)

@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie(key="access_token", path="/")
    return {"message": "Sesi telah ditutup."}
