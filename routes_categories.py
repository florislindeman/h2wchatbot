from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel
from typing import List, Optional
from auth import get_current_admin, get_current_user
from models import TokenData
from database import get_supabase
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/categories", tags=["Categories"])

class CategoryCreate(BaseModel):
    name: str
    description: Optional[str] = None

class Category(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    created_at: str

@router.get("/", response_model=List[Category])
async def get_categories(current_user: TokenData = Depends(get_current_user)):
    """Get all categories (for admins to manage, or user's assigned categories)"""
    supabase = get_supabase()
    
    if current_user.role == "admin":
        # Admins see all categories
        result = supabase.table("categories").select("*").execute()
    else:
        # Regular users see only their assigned categories
        user_cats = supabase.table("user_categories").select("category_id").eq("user_id", current_user.user_id).execute()
        cat_ids = [item["category_id"] for item in user_cats.data]
        
        if not cat_ids:
            return []
        
        result = supabase.table("categories").select("*").in_("id", cat_ids).execute()
    
    return result.data

@router.post("/", response_model=Category, dependencies=[Depends(get_current_admin)])
async def create_category(category: CategoryCreate):
    """Create new category (admin only)"""
    supabase = get_supabase()
    
    # Check if category name already exists
    existing = supabase.table("categories").select("id").eq("name", category.name).execute()
    if existing.data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Category name already exists"
        )
    
    # Create category
    result = supabase.table("categories").insert(category.model_dump()).execute()
    
    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create category"
        )
    
    logger.info(f"New category created: {category.name}")
    return result.data[0]

@router.delete("/{category_id}", dependencies=[Depends(get_current_admin)])
async def delete_category(category_id: str):
    """Delete category (admin only)"""
    supabase = get_supabase()
    
    # Check if category is used by documents
    docs = supabase.table("document_categories").select("document_id").eq("category_id", category_id).execute()
    if docs.data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot delete category: {len(docs.data)} documents are using it"
        )
    
    # Delete user assignments
    supabase.table("user_categories").delete().eq("category_id", category_id).execute()
    
    # Delete category
    result = supabase.table("categories").delete().eq("id", category_id).execute()
    
    logger.info(f"Category deleted: {category_id}")
    return {"message": "Category deleted successfully"}
