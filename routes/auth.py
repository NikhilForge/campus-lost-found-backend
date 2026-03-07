from fastapi import APIRouter, HTTPException, status, Depends
from models.schemas import UserRegister, UserLogin, Token, UserProfile
from database import get_supabase, get_supabase_admin
from middleware.auth import create_access_token, get_current_user
from datetime import datetime

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=Token, status_code=status.HTTP_201_CREATED)
async def register(user_data: UserRegister):
    db = get_supabase()
    admin_db = get_supabase_admin()

    # Check if email already registered
    existing = (
        admin_db.table("users").select("id").eq("email", user_data.email).execute()
    )
    if existing.data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    # Check student ID uniqueness
    existing_sid = (
        admin_db.table("users")
        .select("id")
        .eq("student_id", user_data.student_id)
        .execute()
    )
    if existing_sid.data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Student ID already registered",
        )

    # Register with Supabase Auth
    try:
        auth_response = db.auth.sign_up(
            {"email": user_data.email, "password": user_data.password}
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Registration failed: {str(e)}",
        )

    if not auth_response.user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to create auth user",
        )

    auth_uid = auth_response.user.id

    # Store profile in users table
    profile_data = {
        "id": auth_uid,
        "email": user_data.email,
        "full_name": user_data.full_name,
        "student_id": user_data.student_id,
        "department": user_data.department,
        "phone": user_data.phone,
        "created_at": datetime.utcnow().isoformat(),
    }

    try:
        admin_db.table("users").insert(profile_data).execute()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create user profile: {str(e)}",
        )

    access_token = create_access_token(data={"sub": auth_uid})
    user_profile = UserProfile(**profile_data)

    return Token(access_token=access_token, user=user_profile)


@router.post("/login", response_model=Token)
async def login(credentials: UserLogin):
    db = get_supabase()
    admin_db = get_supabase_admin()

    try:
        auth_response = db.auth.sign_in_with_password(
            {"email": credentials.email, "password": credentials.password}
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    if not auth_response.user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    # Fetch profile
    profile_result = (
        admin_db.table("users")
        .select("*")
        .eq("id", auth_response.user.id)
        .single()
        .execute()
    )

    if not profile_result.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User profile not found",
        )

    access_token = create_access_token(data={"sub": auth_response.user.id})
    user_profile = UserProfile(**profile_result.data)

    return Token(access_token=access_token, user=user_profile)


@router.get("/me", response_model=UserProfile)
async def get_me(current_user: dict = Depends(get_current_user)):
    return UserProfile(**current_user)


@router.put("/me", response_model=UserProfile)
async def update_profile(
    update_data: dict,
    current_user: dict = Depends(get_current_user),
):
    allowed_fields = {"full_name", "phone", "department"}
    filtered = {k: v for k, v in update_data.items() if k in allowed_fields}

    if not filtered:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No valid fields to update",
        )

    admin_db = get_supabase_admin()
    result = (
        admin_db.table("users")
        .update(filtered)
        .eq("id", current_user["id"])
        .execute()
    )

    return UserProfile(**result.data[0])
