from fastapi import APIRouter, HTTPException, status, Depends
from typing import List
from auth import get_current_admin
from models import UserUpdate
from database import get_supabase
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/users", tags=["Users"])

@router.get("/")
async def get_all_users(current_user = Depends(get_current_admin)):
    """Get all users with their categories (admin only)"""
    supabase = get_supabase()
    
    users_result = supabase.table("users").select("*").execute()
    users = users_result.data
    
    for user in users:
        user_cats = supabase.table("user_categories").select("category_id, categories(id, name)").eq("user_id", user["id"]).execute()
        user["categories"] = [{"id": cat["categories"]["id"], "name": cat["categories"]["name"]} for cat in user_cats.data if cat.get("categories")]
    
    return users

@router.put("/{user_id}")
async def update_user(user_id: str, user_update: UserUpdate, current_user = Depends(get_current_admin)):
    """Update user (admin only)"""
    supabase = get_supabase()
    
    update_data = user_update.model_dump(exclude_unset=True, exclude={"category_ids"})
    
    if update_data:
        supabase.table("users").update(update_data).eq("id", user_id).execute()
    
    if user_update.category_ids is not None:
        supabase.table("user_categories").delete().eq("user_id", user_id).execute()
        
        if user_update.category_ids:
            assignments = [{"user_id": user_id, "category_id": cat_id} for cat_id in user_update.category_ids]
            supabase.table("user_categories").insert(assignments).execute()
    
    return {"message": "User updated"}

@router.delete("/{user_id}")
async def delete_user(user_id: str, current_user = Depends(get_current_admin)):
    """Delete user (admin only)"""
    supabase = get_supabase()
    
    if user_id == current_user.user_id:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")
    
    supabase.table("user_categories").delete().eq("user_id", user_id).execute()
    supabase.table("users").delete().eq("id", user_id).execute()
    
    return {"message": "User deleted"}
