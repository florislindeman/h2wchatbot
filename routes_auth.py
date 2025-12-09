from fastapi import APIRouter, HTTPException, status, Depends
from models import LoginRequest, Token, UserCreate, User
from auth import authenticate_user, create_access_token, get_password_hash, get_current_admin
from database import get_supabase
import logging
from datetime import timedelta
from config import settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["Authentication"])

@router.post("/login", response_model=Token)
async def login(login_data: LoginRequest):
    """Login endpoint"""
    user = authenticate_user(login_data.email, login_data.password)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password"
        )
    
    access_token = create_access_token(
        data={
            "sub": user["id"],
            "email": user["email"],
            "role": user["role"]
        },
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    
    logger.info(f"User logged in: {user['email']}")
    return Token(
    access_token=access_token,
    token_type="bearer",
    email=user["email"],
    role=user["role"]
)

@router.post("/register", response_model=User, dependencies=[Depends(get_current_admin)])
async def register_user(user_data: UserCreate):
    """Register new user (admin only)"""
    supabase = get_supabase()
    
    # Check if email already exists
    existing = supabase.table("users").select("id").eq("email", user_data.email).execute()
    if existing.data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Hash password
    password_hash = get_password_hash(user_data.password)
    
    # Create user
    user_dict = user_data.model_dump(exclude={"password", "category_ids"})
    user_dict["password_hash"] = password_hash
    
    result = supabase.table("users").insert(user_dict).execute()
    
    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create user"
        )
    
    user_id = result.data[0]["id"]
    
    # Assign categories
    if user_data.category_ids:
        category_assignments = [
            {"user_id": user_id, "category_id": cat_id}
            for cat_id in user_data.category_ids
        ]
        supabase.table("user_categories").insert(category_assignments).execute()
    
    logger.info(f"New user registered: {user_data.email}")
    return User(**result.data[0])
@router.post("/generate-hash")
def generate_hash(password: str):
    """Temporary endpoint to generate password hash"""
    from auth import get_password_hash
    hash = get_password_hash(password)
    return {"password": password, "hash": hash, "length": len(hash)}
