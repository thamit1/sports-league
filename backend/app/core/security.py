from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from app.core.config import settings
from app.core.database import get_db, execute_query
import sqlite3

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def hash_password(password: str) -> str:
    # bcrypt requires bytes and has a 72-byte limit
    return bcrypt.hashpw(password.encode('utf-8')[:72], bcrypt.gensalt()).decode('utf-8')


def verify_password(plain: str, hashed: str) -> bool:
    # bcrypt requires bytes and has a 72-byte limit
    return bcrypt.checkpw(plain.encode('utf-8')[:72], hashed.encode('utf-8'))


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )


def get_current_user(token: str = Depends(oauth2_scheme)):
    from app.models.models import User
    payload = decode_token(token)
    user_id: int = payload.get("sub")
    if user_id is None:
        raise HTTPException(status_code=401, detail="Invalid token payload")

    user_data = execute_query(
        "SELECT * FROM users WHERE id = ? AND is_active = 1",
        (int(user_id),),
        fetch_one=True
    )

    if not user_data:
        raise HTTPException(status_code=401, detail="User not found or inactive")

    role_rows = execute_query(
        "SELECT role FROM user_assignments WHERE user_id = ? AND scope_type = 'global' AND scope_id IS NULL",
        (int(user_id),), fetch_all=True,
    ) or []
    role_list = sorted({(r['role'] or '').lower() for r in role_rows if r.get('role')})

    return User(
        id=user_data['id'],
        email=user_data['email'],
        phone=user_data['phone'],
        password_hash=user_data['password_hash'],
        first_name=user_data['first_name'],
        last_name=user_data['last_name'],
        role=(user_data['role'] or '').lower(),
        club_id=user_data['club_id'],
        global_player_id=user_data['global_player_id'],
        avatar_url=user_data['avatar_url'],
        date_of_birth=user_data['date_of_birth'],
        gender=user_data['gender'],
        is_active=user_data['is_active'],
        is_verified=bool(user_data.get('is_verified', 0)),
        password_reset_required=bool(user_data.get('password_reset_required', 0)),
        created_at=user_data['created_at'],
        updated_at=user_data['updated_at'],
        roles=role_list,
    )


def get_user_roles(user_id: int, scope_type: str = "global", scope_id=None) -> set:
    """All roles a user holds at the given scope. 'global' scope = capability-level roles."""
    if scope_id is None:
        rows = execute_query(
            "SELECT role FROM user_assignments WHERE user_id = ? AND scope_type = ? AND scope_id IS NULL",
            (user_id, scope_type), fetch_all=True,
        ) or []
    else:
        rows = execute_query(
            "SELECT role FROM user_assignments WHERE user_id = ? AND scope_type = ? AND scope_id = ?",
            (user_id, scope_type, scope_id), fetch_all=True,
        ) or []
    return {(r['role'] or '').lower() for r in rows if r.get('role')}


def has_role(user_id: int, role: str, scope_type: str = "global", scope_id=None) -> bool:
    return role.lower() in get_user_roles(user_id, scope_type, scope_id)


def user_has_any_role(user, required) -> bool:
    """True if user holds any of `required` at global scope (or via legacy users.role fallback)."""
    required_l = {(r.value if hasattr(r, 'value') else r).lower() for r in required}
    if get_user_roles(user.id, "global") & required_l:
        return True
    # Fallback: respect users.role for resilience during transition
    return (user.role or '').lower() in required_l


def require_roles(*roles):
    """
    Allow the request only if the current user holds *any* of `roles` at global scope.
    Reads from user_assignments (Phase 2 source of truth). Falls back to users.role for safety.
    """
    def _dependency(current_user=Depends(get_current_user)):
        if not user_has_any_role(current_user, roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Required role(s): {', '.join((r.value if hasattr(r,'value') else r) for r in roles)}",
            )
        return current_user
    return _dependency

