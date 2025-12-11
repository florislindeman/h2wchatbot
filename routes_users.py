from fastapi import APIRouter, HTTPException, status, Depends
from typing import List, Optional
from pydantic import BaseModel
from auth import get_current_admin
from models import User, UserUpdate
from database import get_supabase
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/users", tags=["Users"])

@router.get("/", response_model=List[dict])
async def get_all_users(current_user = Depends(get_current_admin)):
    """Get all users with their categories (admin only)"""
    supabase = get_supabase()
    
    # Get all users
    users_result = supabase.table("users").select("*").execute()
    users = users_result.data
    
    # Get categories for each user
    for user in users:
        user_cats = supabase.table("user_categories").select("category_id, categories(id, name)").eq("user_id", user["id"]).execute()
        user["categories"] = [{"id": cat["categories"]["id"], "name": cat["categories"]["name"]} for cat in user_cats.data]
    
    return users

@router.put("/{user_id}")
async def update_user(user_id: str, user_update: UserUpdate, current_user = Depends(get_current_admin)):
    """Update user details (admin only)"""
    supabase = get_supabase()
    
    update_data = user_update.model_dump(exclude_unset=True, exclude={"category_ids"})
    
    if update_data:
        result = supabase.table("users").update(update_data).eq("id", user_id).execute()
        
        if not result.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
    
    # Update categories if provided
    if user_update.category_ids is not None:
        # Delete existing assignments
        supabase.table("user_categories").delete().eq("user_id", user_id).execute()
        
        # Add new assignments
        if user_update.category_ids:
            category_assignments = [
                {"user_id": user_id, "category_id": cat_id}
                for cat_id in user_update.category_ids
            ]
            supabase.table("user_categories").insert(category_assignments).execute()
    
    logger.info(f"User updated: {user_id}")
    return {"message": "User updated successfully"}

@router.delete("/{user_id}")
async def delete_user(user_id: str, current_user = Depends(get_current_admin)):
    """Delete user (admin only)"""
    supabase = get_supabase()
    
    # Don't allow deleting yourself
    if user_id == current_user.user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete your own account"
        )
    
    # Delete user category assignments
    supabase.table("user_categories").delete().eq("user_id", user_id).execute()
    
    # Delete user
    result = supabase.table("users").delete().eq("id", user_id).execute()
    
    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    logger.info(f"User deleted: {user_id}")
    return {"message": "User deleted successfully"}
