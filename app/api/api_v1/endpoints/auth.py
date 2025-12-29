from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.auth import get_supabase_auth_client, verify_supabase_token, admin_find_user_by_phone
from app.core.logging import get_logger
from app.schemas.user import UserCreate, UserLogin, User as UserSchema
from app.services.user import get_or_create_user_from_supabase
import anyio
from pydantic import BaseModel

router = APIRouter()
logger = get_logger(__name__)

@router.post("/login/")
async def login(user_login: UserLogin, db: AsyncSession = Depends(get_db)):
    """Login with Supabase Auth using phone + password"""
    try:
        supabase = get_supabase_auth_client()
        data = await anyio.to_thread.run_sync(
            lambda: supabase.auth.sign_in_with_password({
                "phone": user_login.phone,
                "password": user_login.password,
            })
        )

        # If the response lacks a usable session/token, try to classify the cause
        if not getattr(data, "session", None) or not getattr(data.session, "access_token", None):
            # Attempt admin lookup to distinguish not found vs wrong password
            supa_user = await admin_find_user_by_phone(user_login.phone)
            if not supa_user:
                logger.warning("Login failed: user not found (admin lookup)", extra={"phone": user_login.phone})
                raise HTTPException(
                    status_code=404,
                    detail={
                        "code": "USER_NOT_FOUND",
                        "message": "User with this phone does not exist",
                    },
                )
            logger.warning("Login failed: invalid credentials", extra={"phone": user_login.phone})
            raise HTTPException(
                status_code=401,
                detail={
                    "code": "INVALID_CREDENTIALS",
                    "message": "Invalid phone or password",
                },
            )

        # Verify token and ensure account is verified where applicable
        supabase_user_data = await verify_supabase_token(data.session.access_token)
        if not supabase_user_data:
            raise HTTPException(
                status_code=401,
                detail={
                    "code": "TOKEN_INVALID",
                    "message": "Invalid or expired token",
                },
            )

        if not supabase_user_data.get("email_verified", False):
            logger.warning("Login blocked: unverified account", extra={"phone": user_login.phone})
            raise HTTPException(
                status_code=403,
                detail={
                    "code": "UNVERIFIED_ACCOUNT",
                    "message": "Please verify your email or phone before logging in",
                },
            )

        db_user = await get_or_create_user_from_supabase(db, supabase_user_data)

        return {
            "access_token": data.session.access_token,
            "token_type": "bearer",
            "user": db_user,
        }
    except HTTPException:
        # Re-raise structured exceptions
        raise
    except Exception as e:
        # Heuristic classification for common Supabase auth errors
        msg = str(e).lower()

        if any(k in msg for k in ["confirm", "verified", "verification"]):
            logger.error(f"Authentication failed (unverified): {e}", extra={"phone": user_login.phone})
            raise HTTPException(
                status_code=403,
                detail={
                    "code": "UNVERIFIED_ACCOUNT",
                    "message": "Please verify your email or phone before logging in",
                },
            )
        if any(k in msg for k in ["too many", "rate", "rate limit", "throttle"]):
            logger.error(f"Authentication rate limited: {e}", extra={"phone": user_login.phone})
            raise HTTPException(
                status_code=429,
                detail={
                    "code": "RATE_LIMITED",
                    "message": "Too many attempts. Please try again later",
                },
            )

        # Try admin lookup as a fallback to classify not found vs invalid password
        try:
            supa_user = await admin_find_user_by_phone(user_login.phone)
        except Exception:
            supa_user = None

        if not supa_user:
            logger.error(f"Authentication failed: user not found ({e})", extra={"phone": user_login.phone})
            raise HTTPException(
                status_code=404,
                detail={
                    "code": "USER_NOT_FOUND",
                    "message": "User with this phone does not exist",
                },
            )

        logger.error(f"Authentication failed: invalid credentials ({e})", extra={"phone": user_login.phone})
        raise HTTPException(
            status_code=401,
            detail={
                "code": "INVALID_CREDENTIALS",
                "message": "Invalid phone or password",
            },
        )

@router.post("/register/")
async def register(user_data: UserCreate, db: AsyncSession = Depends(get_db)):
    """Register via Supabase Auth using phone as primary identifier"""
    try:
        supabase = get_supabase_auth_client()
        data = await anyio.to_thread.run_sync(
            lambda: supabase.auth.sign_up({
                "phone": user_data.phone,
                "password": user_data.password,
                "options": {
                    "data": {
                        "full_name": user_data.full_name,
                        "email": user_data.email
                    }
                }
            })
        )
        
        if data.user:
            supabase_user_data = {
                "id": data.user.id,
                "phone": data.user.phone,
                "email": data.user.email,
                "user_metadata": data.user.user_metadata or {}
            }
            
            db_user = await get_or_create_user_from_supabase(db, supabase_user_data)
            
            return {
                "message": "User registered successfully",
                "user": db_user,
                "access_token": data.session.access_token if data.session else None
            }
        else:
            raise HTTPException(
                status_code=400,
                detail={
                    "code": "REGISTRATION_FAILED",
                    "message": "Registration failed",
                },
            )
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "REGISTRATION_FAILED",
                "message": f"Registration failed: {str(e)}",
            },
        )


class OTPRequest(BaseModel):
    phone: str


@router.post("/otp/request")
async def request_otp(payload: OTPRequest):
    """Request an OTP for phone login (Supabase passwordless OTP)."""
    try:
        supabase = get_supabase_auth_client()
        await anyio.to_thread.run_sync(
            lambda: supabase.auth.sign_in_with_otp({"phone": payload.phone})
        )
        return {"message": "OTP sent"}
    except Exception as e:
        logger.error(f"OTP request failed: {e}", extra={"phone": payload.phone})
        raise HTTPException(
            status_code=400,
            detail={
                "code": "OTP_REQUEST_FAILED",
                "message": "Failed to send OTP",
            },
        )


class OTPVerify(BaseModel):
    phone: str
    token: str
    type: Literal["sms", "phone_change"] = "sms"


@router.post("/otp/verify")
async def verify_otp(payload: OTPVerify, db: AsyncSession = Depends(get_db)):
    """Verify an OTP and return a bearer token + local user record."""
    try:
        supabase = get_supabase_auth_client()
        auth_resp = await anyio.to_thread.run_sync(
            lambda: supabase.auth.verify_otp(
                {
                    "phone": payload.phone,
                    "token": payload.token,
                    "type": payload.type,
                }
            )
        )

        session = getattr(auth_resp, "session", None)
        access_token = getattr(session, "access_token", None) if session else None
        if not access_token:
            raise HTTPException(
                status_code=401,
                detail={
                    "code": "OTP_INVALID",
                    "message": "Invalid or expired OTP",
                },
            )

        supabase_user_data = await verify_supabase_token(access_token)
        if not supabase_user_data:
            raise HTTPException(
                status_code=401,
                detail={
                    "code": "TOKEN_INVALID",
                    "message": "Invalid or expired token",
                },
            )

        db_user = await get_or_create_user_from_supabase(db, supabase_user_data)

        return {
            "access_token": access_token,
            "token_type": "bearer",
            "user": db_user,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"OTP verify failed: {e}", extra={"phone": payload.phone})
        raise HTTPException(
            status_code=400,
            detail={
                "code": "OTP_VERIFY_FAILED",
                "message": "OTP verification failed",
            },
        )
