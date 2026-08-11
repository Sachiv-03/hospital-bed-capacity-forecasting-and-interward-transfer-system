from datetime import timedelta
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_active_user, get_db
from app.core.config import settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    get_password_hash,
    verify_password,
)
from app.models.user import User, UserRole
from app.models.hospital import Hospital
from app.schemas.token import RefreshTokenRequest, Token
from app.schemas.user import UserCreate, UserLogin, UserResponse

router = APIRouter()


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register New User Account",
    description="Registers a new healthcare staff member with role (Super Admin, Admin, Doctor, Nurse, Receptionist).",
)
def register(
    user_in: UserCreate,
    db: Session = Depends(get_db),
) -> Any:
    """Register user with email uniqueness check, hospital association, and bcrypt password hashing."""
    existing_user = db.query(User).filter(User.email == user_in.email.lower()).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A user with this email address already exists in the system.",
        )

    user_role_str = user_in.role.value if hasattr(user_in.role, 'value') else str(user_in.role)
    target_hospital_id = user_in.hospital_id

    # If normal hospital user and no hospital_id provided, default to the first available hospital
    if user_role_str != UserRole.SUPER_ADMIN.value and not target_hospital_id:
        first_h = db.query(Hospital).order_by(Hospital.id.asc()).first()
        if first_h:
            target_hospital_id = first_h.id

    new_user = User(
        full_name=user_in.full_name,
        email=user_in.email.lower(),
        password_hash=get_password_hash(user_in.password),
        role=user_role_str,
        hospital_id=target_hospital_id,
        is_active=True,
    )
    
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    hospital_name = None
    if new_user.hospital_id:
        h = db.query(Hospital).filter(Hospital.id == new_user.hospital_id).first()
        if h:
            hospital_name = h.name

    return {
        "id": new_user.id,
        "email": new_user.email,
        "full_name": new_user.full_name,
        "role": new_user.role,
        "hospital_id": new_user.hospital_id,
        "hospital_name": hospital_name,
        "is_active": new_user.is_active,
        "created_at": new_user.created_at,
        "updated_at": new_user.updated_at,
    }


@router.post(
    "/login",
    response_model=Token,
    summary="User Login & JWT Token Issue",
    description="Authenticates user credentials and issues Access and Refresh tokens.",
)
def login(
    user_in: UserLogin,
    db: Session = Depends(get_db),
) -> Any:
    """Authenticate user with email/password and issue JWT tokens."""
    user = db.query(User).filter(User.email == user_in.email.lower()).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password.",
        )

    if not verify_password(user_in.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password.",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user account. Contact hospital administrator.",
        )

    access_token = create_access_token(subject=user.id, role=user.role)
    refresh_token = create_refresh_token(subject=user.id, role=user.role)

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    }


@router.post(
    "/refresh",
    response_model=Token,
    summary="Refresh Access Token",
    description="Validates JWT Refresh token and issues a fresh Access and Refresh token pair.",
)
def refresh_token(
    refresh_in: RefreshTokenRequest,
    db: Session = Depends(get_db),
) -> Any:
    """Refresh access token using valid refresh token."""
    payload = decode_token(refresh_in.refresh_token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    if payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type provided for refresh",
        )

    user_id_str = payload.get("sub")
    if not user_id_str:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )

    try:
        user_id = int(user_id_str)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid user identification in token",
        )

    user = db.query(User).filter(User.id == user_id).first()
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User associated with refresh token is inactive or no longer exists",
        )

    new_access_token = create_access_token(subject=user.id, role=user.role)
    new_refresh_token = create_refresh_token(subject=user.id, role=user.role)

    return {
        "access_token": new_access_token,
        "refresh_token": new_refresh_token,
        "token_type": "bearer",
        "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    }


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get Current User Profile",
    description="Returns the profile details of the currently authenticated user.",
)
def read_current_user(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """Return profile information of current logged-in user with hospital details."""
    hospital_name = None
    if current_user.hospital_id:
        h = db.query(Hospital).filter(Hospital.id == current_user.hospital_id).first()
        if h:
            hospital_name = h.name

    return {
        "id": current_user.id,
        "email": current_user.email,
        "full_name": current_user.full_name,
        "role": current_user.role,
        "hospital_id": current_user.hospital_id,
        "hospital_name": hospital_name,
        "is_active": current_user.is_active,
        "created_at": current_user.created_at,
        "updated_at": current_user.updated_at,
    }


@router.post(
    "/logout",
    summary="User Logout",
    description="Logs out user and invalidates client session state.",
)
def logout(
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """Logout current user."""
    return {"message": "Successfully logged out user session"}
