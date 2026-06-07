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
    UserAssignmentCreate,
    UserAssignmentOut,
)
from typing import List
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

    # Phase 2: mirror primary role into user_assignments at global scope
    execute_query(
        """INSERT OR IGNORE INTO user_assignments (user_id, scope_type, scope_id, role, granted_at)
           VALUES (?, 'global', NULL, ?, CURRENT_TIMESTAMP)""",
        (user_id, UserRole.VIEWER.value),
    )

    user_row = execute_query(
        "SELECT * FROM users WHERE id = ?",
        (user_id,),
        fetch_one=True
    )

    return _user_response(user_row)


def _user_response(user_row: dict) -> dict:
    """Build a UserOut-shaped dict from a users-row + their global-scope assignments."""
    role_rows = execute_query(
        "SELECT role FROM user_assignments WHERE user_id = ? AND scope_type = 'global' AND scope_id IS NULL",
        (user_row['id'],), fetch_all=True,
    ) or []
    roles = sorted({(r['role'] or '').lower() for r in role_rows if r.get('role')})
    captain_rows = execute_query(
        "SELECT scope_id FROM user_assignments WHERE user_id = ? AND scope_type = 'team' AND role = 'captain'",
        (user_row['id'],), fetch_all=True,
    ) or []
    captain_team_ids = sorted({r['scope_id'] for r in captain_rows if r.get('scope_id')})
    return {
        "id": user_row['id'],
        "email": user_row['email'],
        "first_name": user_row['first_name'],
        "last_name": user_row['last_name'],
        "full_name": f"{user_row['first_name']} {user_row['last_name']}",
        "role": (user_row['role'] or '').lower(),
        "roles": roles,
        "captain_team_ids": captain_team_ids,
        "club_id": user_row['club_id'],
        "global_player_id": user_row['global_player_id'],
        "avatar_url": user_row['avatar_url'],
        "gender": user_row['gender'],
        "is_active": bool(user_row['is_active']),
        "is_verified": bool(user_row.get('is_verified', 0)),
        "password_reset_required": bool(user_row.get('password_reset_required', 0)),
        "created_at": user_row['created_at'],
    }


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
        "user": _user_response(user_row),
    }


@router.get("/me", response_model=UserOut)
def me(current_user: User = Depends(get_current_user)):
    row = execute_query("SELECT * FROM users WHERE id = ?", (current_user.id,), fetch_one=True)
    return _user_response(row)


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

    # Phase 2: when primary role changes, ensure it exists in user_assignments at global scope.
    # We don't remove other roles the user holds — only ensure the new primary is present.
    if 'role' in updates:
        execute_query(
            """INSERT OR IGNORE INTO user_assignments (user_id, scope_type, scope_id, role, granted_by, granted_at)
               VALUES (?, 'global', NULL, ?, ?, CURRENT_TIMESTAMP)""",
            (user_id, updates['role'], current_user.id),
        )

    user_row = execute_query(
        "SELECT * FROM users WHERE id = ?",
        (user_id,),
        fetch_one=True
    )
    return _user_response(user_row)


# ── User-assignment CRUD (Phase 2: multi-role) ──────────────────────────

@router.get("/users/{user_id}/assignments", response_model=List[UserAssignmentOut])
def list_user_assignments(user_id: int, current_user: User = Depends(get_current_user)):
    if current_user.role not in (UserRole.SUPER_ADMIN.value, UserRole.CLUB_ADMIN.value) and current_user.id != user_id:
        raise HTTPException(status_code=403, detail="Cannot view another user's role assignments")
    rows = execute_query(
        """SELECT a.*, (u.first_name || ' ' || u.last_name) AS granted_by_name
             FROM user_assignments a
             LEFT JOIN users u ON u.id = a.granted_by
            WHERE a.user_id = ?
            ORDER BY a.scope_type, a.role""",
        (user_id,), fetch_all=True,
    ) or []
    return rows


@router.post("/users/{user_id}/assignments", response_model=UserAssignmentOut, status_code=201)
def grant_user_assignment(user_id: int, payload: UserAssignmentCreate,
                          current_user: User = Depends(get_current_user)):
    if current_user.role not in (UserRole.SUPER_ADMIN.value, UserRole.CLUB_ADMIN.value):
        raise HTTPException(status_code=403, detail="Required role(s): super_admin, club_admin")
    if current_user.role == UserRole.CLUB_ADMIN.value and payload.role == UserRole.SUPER_ADMIN.value:
        raise HTTPException(status_code=403, detail="Club admins cannot grant super_admin")

    user = execute_query("SELECT id FROM users WHERE id = ?", (user_id,), fetch_one=True)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    try:
        aid = execute_query(
            """INSERT INTO user_assignments (user_id, scope_type, scope_id, role, granted_by, granted_at)
               VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)""",
            (user_id, payload.scope_type, payload.scope_id, payload.role.lower(), current_user.id),
            return_lastid=True,
        )
    except Exception as exc:
        raise HTTPException(status_code=409, detail=f"Assignment already exists: {exc}")
    row = execute_query(
        """SELECT a.*, (u.first_name || ' ' || u.last_name) AS granted_by_name
             FROM user_assignments a LEFT JOIN users u ON u.id = a.granted_by
            WHERE a.id = ?""",
        (aid,), fetch_one=True,
    )
    return row


# Precedence used to pick a fallback primary role when the current one is revoked.
# Higher index = higher priority.
_ROLE_PRECEDENCE = ['viewer', 'player', 'official', 'score_keeper', 'club_manager', 'club_admin', 'super_admin']


def _sync_primary_after_revoke(user_id: int, revoked_role: str, user_row: dict):
    """If the revoked role matched users.role, demote primary to next-highest remaining."""
    current_primary = (user_row.get('role') or '').lower()
    if current_primary != revoked_role.lower():
        return
    remaining = execute_query(
        "SELECT role FROM user_assignments WHERE user_id = ? AND scope_type = 'global' AND scope_id IS NULL",
        (user_id,), fetch_all=True,
    ) or []
    remaining_roles = [(r['role'] or '').lower() for r in remaining if r.get('role')]
    if remaining_roles:
        best = max(remaining_roles, key=lambda r: _ROLE_PRECEDENCE.index(r) if r in _ROLE_PRECEDENCE else -1)
    else:
        best = UserRole.VIEWER.value
    execute_query(
        "UPDATE users SET role = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (best, user_id),
    )


@router.delete("/users/{user_id}/assignments/{assignment_id}", status_code=204)
def revoke_user_assignment(user_id: int, assignment_id: int,
                            current_user: User = Depends(get_current_user)):
    if current_user.role not in (UserRole.SUPER_ADMIN.value, UserRole.CLUB_ADMIN.value):
        raise HTTPException(status_code=403, detail="Required role(s): super_admin, club_admin")
    row = execute_query(
        "SELECT id, role, scope_type FROM user_assignments WHERE id = ? AND user_id = ?",
        (assignment_id, user_id), fetch_one=True,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Assignment not found")
    if current_user.role == UserRole.CLUB_ADMIN.value and row['role'] == UserRole.SUPER_ADMIN.value:
        raise HTTPException(status_code=403, detail="Club admins cannot revoke super_admin")

    user_row = execute_query("SELECT id, role FROM users WHERE id = ?", (user_id,), fetch_one=True)
    execute_query("DELETE FROM user_assignments WHERE id = ?", (assignment_id,))

    # If we just revoked the user's primary role at global scope, fix users.role too
    if row['scope_type'] == 'global' and user_row:
        _sync_primary_after_revoke(user_id, row['role'], user_row)


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
