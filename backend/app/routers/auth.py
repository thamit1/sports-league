from fastapi import APIRouter, Depends, HTTPException, status
from app.core.database import execute_query
from app.core.security import hash_password, verify_password, create_access_token, get_current_user
from app.models.models import User, UserRole
from app.schemas.schemas import (
    RegisterRequest,
    LoginRequest,
    TokenResponse,
    UserOut,
    UserAdminUpdate,
    PasswordChangeRequest,
)
import uuid

router = APIRouter()


@router.post("/register", response_model=UserOut, status_code=201)
def register(payload: RegisterRequest):
    user_row = execute_query(
        "SELECT id FROM users WHERE email = ?",
        (payload.email,),
        fetch_one=True
    )
    if user_row:
        raise HTTPException(status_code=400, detail="Email already registered")

    global_player_id = f"SLMS-{uuid.uuid4().hex[:8].upper()}"
    user_id = execute_query(
        """INSERT INTO users
           (email, password_hash, first_name, last_name, phone, role, club_id, global_player_id, is_active, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)""",
        (
            payload.email,
            hash_password(payload.password),
            payload.first_name,
            payload.last_name,
            payload.phone,
            UserRole.VIEWER.value,
            payload.club_id,
            global_player_id,
        ),
        return_lastid=True
    )

    user_row = execute_query(
        "SELECT * FROM users WHERE id = ?",
        (user_id,),
        fetch_one=True
    )

    return User(
        id=user_row['id'],
        email=user_row['email'],
        phone=user_row['phone'],
        password_hash=user_row['password_hash'],
        first_name=user_row['first_name'],
        last_name=user_row['last_name'],
        role=user_row['role'],
        club_id=user_row['club_id'],
        global_player_id=user_row['global_player_id'],
        avatar_url=user_row['avatar_url'],
        date_of_birth=user_row['date_of_birth'],
        gender=user_row['gender'],
        is_active=user_row['is_active'],
        is_verified=user_row['is_verified'],
        created_at=user_row['created_at'],
        updated_at=user_row['updated_at'],
    )


@router.post("/login")
def login(payload: LoginRequest):
    user_row = execute_query(
        "SELECT * FROM users WHERE email = ?",
        (payload.email,),
        fetch_one=True
    )

    if not user_row or not verify_password(payload.password, user_row['password_hash']):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    if not user_row['is_active']:
        raise HTTPException(status_code=403, detail="Account is inactive")

    normalized_role = (user_row['role'] or '').lower()
    token = create_access_token({"sub": str(user_row['id']), "role": normalized_role})
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": user_row['id'],
            "email": user_row['email'],
            "first_name": user_row['first_name'],
            "last_name": user_row['last_name'],
            "full_name": f"{user_row['first_name']} {user_row['last_name']}",
            "role": normalized_role,
            "club_id": user_row['club_id'],
            "global_player_id": user_row['global_player_id'],
            "avatar_url": user_row['avatar_url'],
            "gender": user_row['gender'],
            "is_active": user_row['is_active'],
            "is_verified": user_row['is_verified'],
            "password_reset_required": bool(user_row.get('password_reset_required', 0)),
            "created_at": user_row['created_at'],
        },
    }


@router.get("/me", response_model=UserOut)
def me(current_user: User = Depends(get_current_user)):
    return current_user


@router.patch("/users/{user_id}", response_model=UserOut)
def update_user(user_id: int, payload: UserAdminUpdate, current_user: User = Depends(get_current_user)):
    if current_user.role not in (UserRole.SUPER_ADMIN.value, UserRole.CLUB_ADMIN.value):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Required role(s): super_admin, club_admin")

    if current_user.role == UserRole.CLUB_ADMIN.value and payload.role == UserRole.SUPER_ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Club admins cannot assign super_admin role")

    user_row = execute_query(
        "SELECT * FROM users WHERE id = ?",
        (user_id,),
        fetch_one=True
    )
    if not user_row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    updates = {}
    if payload.role is not None:
        updates['role'] = payload.role.value
    if payload.temporary_password is not None:
        if current_user.role != UserRole.SUPER_ADMIN.value:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only super admins can reset passwords")
        updates['password_hash'] = hash_password(payload.temporary_password)
        updates['password_reset_required'] = 1
    if payload.password_reset_required is not None:
        if current_user.role != UserRole.SUPER_ADMIN.value:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only super admins can reset passwords")
        updates['password_reset_required'] = 1 if payload.password_reset_required else 0
    if payload.is_active is not None:
        updates['is_active'] = 1 if payload.is_active else 0
    if payload.first_name is not None:
        updates['first_name'] = payload.first_name
    if payload.last_name is not None:
        updates['last_name'] = payload.last_name
    if payload.phone is not None:
        updates['phone'] = payload.phone
    if payload.avatar_url is not None:
        updates['avatar_url'] = payload.avatar_url
    if payload.date_of_birth is not None:
        updates['date_of_birth'] = payload.date_of_birth.isoformat()
    if payload.gender is not None:
        updates['gender'] = payload.gender

    if updates:
        columns = ', '.join([f"{key} = ?" for key in updates.keys()])
        execute_query(
            f"UPDATE users SET {columns}, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            tuple(updates.values()) + (user_id,)
        )

    user_row = execute_query(
        "SELECT * FROM users WHERE id = ?",
        (user_id,),
        fetch_one=True
    )
    return User(
        id=user_row['id'],
        email=user_row['email'],
        phone=user_row['phone'],
        password_hash=user_row['password_hash'],
        first_name=user_row['first_name'],
        last_name=user_row['last_name'],
        role=(user_row['role'] or '').lower(),
        club_id=user_row['club_id'],
        global_player_id=user_row['global_player_id'],
        avatar_url=user_row['avatar_url'],
        date_of_birth=user_row['date_of_birth'],
        gender=user_row['gender'],
        is_active=user_row['is_active'],
        is_verified=user_row['is_verified'],
        password_reset_required=bool(user_row.get('password_reset_required', 0)),
        created_at=user_row['created_at'],
        updated_at=user_row['updated_at'],
    )


@router.post("/change-password")
def change_password(payload: PasswordChangeRequest, current_user: User = Depends(get_current_user)):
    if not current_user.password_reset_required:
        if not payload.old_password or not verify_password(payload.old_password, current_user.password_hash):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid current password")

    execute_query(
        "UPDATE users SET password_hash = ?, password_reset_required = 0, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (hash_password(payload.new_password), current_user.id)
    )
    return {"detail": "Password changed successfully"}
