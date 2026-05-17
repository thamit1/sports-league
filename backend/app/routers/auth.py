from fastapi import APIRouter, Depends, HTTPException, status
from app.core.database import execute_query
from app.core.security import hash_password, verify_password, create_access_token, get_current_user
from app.models.models import User
from app.schemas.schemas import RegisterRequest, LoginRequest, TokenResponse, UserOut
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
           (email, password_hash, first_name, last_name, phone, role, club_id, global_player_id)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            payload.email,
            hash_password(payload.password),
            payload.first_name,
            payload.last_name,
            payload.phone,
            payload.role,
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

    token = create_access_token({"sub": str(user_row['id']), "role": user_row['role']})
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": user_row['id'],
            "email": user_row['email'],
            "first_name": user_row['first_name'],
            "last_name": user_row['last_name'],
            "full_name": f"{user_row['first_name']} {user_row['last_name']}",
            "role": user_row['role'],
            "club_id": user_row['club_id'],
            "global_player_id": user_row['global_player_id'],
            "avatar_url": user_row['avatar_url'],
            "gender": user_row['gender'],
            "is_active": user_row['is_active'],
            "is_verified": user_row['is_verified'],
            "created_at": user_row['created_at'],
        },
    }


@router.get("/me", response_model=UserOut)
def me(current_user: User = Depends(get_current_user)):
    return current_user
