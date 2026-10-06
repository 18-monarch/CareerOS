from argon2.exceptions import InvalidHashError, VerificationError
from careeros.config import get_settings
from careeros.db import get_db, utcnow
from careeros.models import AuditLog, AuthSession, Preferences, Profile, User
from careeros.schemas import Credentials, PasswordChange, PreferenceIn
from careeros.security import (
    DUMMY_HASH,
    current_user,
    digest,
    hasher,
    rate_limit,
    set_tokens,
    verify_csrf,
)
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

router = APIRouter(prefix="/auth", tags=["Authentication"])


def protect_login(request, db, email):
    origin = request.headers.get("origin")
    if origin and origin != get_settings().frontend_origin:
        raise HTTPException(403, "Origin not allowed")
    rate_limit(db, f"auth-email:{email.lower()}")
    rate_limit(db, f"auth-ip:{request.client.host if request.client else 'unknown'}", limit=100)


@router.post("/register", status_code=201)
def register(
    body: Credentials, request: Request, response: Response, db: Session = Depends(get_db)
):
    if not get_settings().registration_enabled:
        raise HTTPException(403, "Registration is disabled")
    protect_login(request, db, body.email)
    user = User(email=body.email.lower(), name=body.name, password_hash=hasher.hash(body.password))
    db.add(user)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "Unable to register this email") from exc
    db.add_all(
        [
            Profile(user_id=user.id),
            Preferences(user_id=user.id, data=PreferenceIn().model_dump()),
            AuditLog(user_id=user.id, action="registered"),
        ]
    )
    tokens = set_tokens(db, response, user.id)
    return {"id": user.id, "name": user.name, **tokens}


@router.post("/login")
def login(body: Credentials, request: Request, response: Response, db: Session = Depends(get_db)):
    protect_login(request, db, body.email)
    user = db.scalar(select(User).where(User.email == body.email.lower()))
    try:
        hasher.verify(user.password_hash if user else DUMMY_HASH, body.password)
    except (VerificationError, InvalidHashError) as exc:
        raise HTTPException(401, "Invalid email or password") from exc
    if not user:
        raise HTTPException(401, "Invalid email or password")
    if hasher.check_needs_rehash(user.password_hash):
        user.password_hash = hasher.hash(body.password)
    db.add(AuditLog(user_id=user.id, action="login"))
    return {"id": user.id, "name": user.name, **set_tokens(db, response, user.id)}


@router.post("/refresh")
def refresh(request: Request, response: Response, db: Session = Depends(get_db)):
    session = db.scalar(
        select(AuthSession)
        .where(
            AuthSession.refresh_hash == digest(request.cookies.get("career_refresh", "")),
            AuthSession.expires > utcnow(),
        )
        .with_for_update()
    )
    if not session:
        raise HTTPException(401, "Session expired")
    verify_csrf(request, session)
    return set_tokens(db, response, session.user_id, session)


@router.get("/me")
def me(user: User = Depends(current_user)):
    return {"id": user.id, "name": user.name, "email": user.email}


@router.post("/password")
def change_password(
    body: PasswordChange,
    response: Response,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    rate_limit(db, f"password:{user.id}", 5, 900)
    user = db.scalar(
        select(User)
        .where(User.id == user.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    try:
        hasher.verify(user.password_hash, body.current_password)
    except (VerificationError, InvalidHashError) as exc:
        raise HTTPException(400, "Current password is incorrect") from exc
    user.password_hash = hasher.hash(body.new_password)
    db.execute(delete(AuthSession).where(AuthSession.user_id == user.id))
    db.add(AuditLog(user_id=user.id, action="password.changed"))
    return {"ok": True, **set_tokens(db, response, user.id)}


@router.post("/logout")
def logout(
    request: Request,
    response: Response,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    db.execute(
        delete(AuthSession).where(
            AuthSession.user_id == user.id,
            AuthSession.access_hash == digest(request.cookies.get("career_access", "")),
        )
    )
    db.commit()
    for name in ["career_access", "career_refresh", "career_csrf"]:
        response.delete_cookie(
            name,
            path="/",
            secure=get_settings().cookie_secure,
            httponly=name != "career_csrf",
            samesite="lax",
        )
    return {"ok": True}
