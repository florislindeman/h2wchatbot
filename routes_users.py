from fastapi import APIRouter, HTTPException, status, Depends
from typing import List
from models import User, UserCreate, UserUpdate, UserWithCategories
from auth import get_current_admin, get_current_user, TokenData, get_password_hash
from database import get_supabase
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/users", tags=["Users"])

@router.get("/me", response_model=UserWithCategories)
async def get_current_user_info(current_user: TokenData = Depends(get_current_user)):
    """Get current user information"""
    supabase = get_supabase()
    
    # Get user data
    user_result = supabase.table("users").select("*").eq("id", current_user.user_id).execute()
    if not user_result.data:
        raise HTTPException(status_code=404, detail="User not found")
    
    user = user_result.data[0]
    
    # Get user categories
    cat_result = supabase.table("user_categories").select("category_id").eq("user_id", current_user.user_id).execute()
    category_ids = [item["category_id"] for item in cat_result.data]
    
    return UserWithCategories(**user, categories=category_ids)

@router.get("/", response_model=List[UserWithCategories], dependencies=[Depends(get_current_admin)])
async def list_users():
    """List all users (admin only)"""
    supabase = get_supabase()
    
    result = supabase.table("users").select("*").execute()
    users = []
    
    for user in result.data:
        # Get categories for each user
        cat_result = supabase.table("user_categories").select("category_id").eq("user_id", user["id"]).execute()
        category_ids = [item["category_id"] for item in cat_result.data]
        users.append(UserWithCategories(**user, categories=category_ids))
    
    return users

@router.get("/{user_id}", response_model=UserWithCategories, dependencies=[Depends(get_current_admin)])
async def get_user(user_id: str):
    """Get specific user (admin only)"""
    supabase = get_supabase()
    
    result = supabase.table("users").select("*").eq("id", user_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="User not found")
    
    user = result.data[0]
    
    # Get categories
    cat_result = supabase.table("user_categories").select("category_id").eq("user_id", user_id).execute()
    category_ids = [item["category_id"] for item in cat_result.data]
    
    return UserWithCategories(**user, categories=category_ids)

@router.put("/{user_id}", response_model=UserWithCategories, dependencies=[Depends(get_current_admin)])
async def update_user(user_id: str, user_update: UserUpdate):
    """Update user (admin only)"""
    supabase = get_supabase()
    
    # Check user exists
    existing = supabase.table("users").select("id").eq("id", user_id).execute()
    if not existing.data:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Update user data
    update_dict = user_update.model_dump(exclude_unset=True, exclude={"category_ids"})
    
    if update_dict:
        supabase.table("users").update(update_dict).eq("id", user_id).execute()
    
    # Update categories if provided
    if user_update.category_ids is not None:
        # Delete existing categories
        supabase.table("user_categories").delete().eq("user_id", user_id).execute()
        
        # Insert new categories
        if user_update.category_ids:
            category_assignments = [
                {"user_id": user_id, "category_id": cat_id}
                for cat_id in user_update.category_ids
            ]
            supabase.table("user_categories").insert(category_assignments).execute()
    
    # Get updated user
    result = supabase.table("users").select("*").eq("id", user_id).execute()
    user = result.data[0]
    
    cat_result = supabase.table("user_categories").select("category_id").eq("user_id", user_id).execute()
    category_ids = [item["category_id"] for item in cat_result.data]
    
    logger.info(f"User updated: {user_id}")
    return UserWithCategories(**user, categories=category_ids)

@router.delete("/{user_id}", dependencies=[Depends(get_current_admin)])
async def delete_user(user_id: str):
    """Delete user (admin only)"""
    supabase = get_supabase()
    
    # Delete user categories first
    supabase.table("user_categories").delete().eq("user_id", user_id).execute()
    
    # Delete user
    result = supabase.table("users").delete().eq("id", user_id).execute()
    
    if not result.data:
        raise HTTPException(status_code=404, detail="User not found")
    
    logger.info(f"User deleted: {user_id}")
    return {"message": "User deleted successfully"}
