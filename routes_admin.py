from fastapi import APIRouter, HTTPException, Depends
from typing import List
from models import (
    Department, DepartmentCreate,
    Category, CategoryCreate,
    DashboardStats, DepartmentStats, KnowledgeGap,
    AuditLog
)
from auth import get_current_admin, TokenData
from database import get_supabase
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin", tags=["Admin"])

# Departments
@router.post("/departments", response_model=Department, dependencies=[Depends(get_current_admin)])
async def create_department(dept: DepartmentCreate):
    """Create new department"""
    supabase = get_supabase()
    
    result = supabase.table("departments").insert(dept.model_dump()).execute()
    
    if not result.data:
        raise HTTPException(status_code=500, detail="Failed to create department")
    
    logger.info(f"Department created: {dept.name}")
    return Department(**result.data[0])

@router.get("/departments", response_model=List[Department], dependencies=[Depends(get_current_admin)])
async def list_departments():
    """List all departments"""
    supabase = get_supabase()
    
    result = supabase.table("departments").select("*").execute()
    return [Department(**dept) for dept in result.data]

@router.put("/departments/{dept_id}", response_model=Department, dependencies=[Depends(get_current_admin)])
async def update_department(dept_id: str, dept: DepartmentCreate):
    """Update department"""
    supabase = get_supabase()
    
    result = supabase.table("departments").update(dept.model_dump()).eq("id", dept_id).execute()
    
    if not result.data:
        raise HTTPException(status_code=404, detail="Department not found")
    
    logger.info(f"Department updated: {dept_id}")
    return Department(**result.data[0])

@router.delete("/departments/{dept_id}", dependencies=[Depends(get_current_admin)])
async def delete_department(dept_id: str):
    """Delete department"""
    supabase = get_supabase()
    
    # Check if department has users
    users = supabase.table("users").select("id").eq("department_id", dept_id).execute()
    if users.data:
        raise HTTPException(status_code=400, detail="Cannot delete department with users")
    
    result = supabase.table("departments").delete().eq("id", dept_id).execute()
    
    if not result.data:
        raise HTTPException(status_code=404, detail="Department not found")
    
    logger.info(f"Department deleted: {dept_id}")
    return {"message": "Department deleted"}

# Categories
@router.post("/categories", response_model=Category, dependencies=[Depends(get_current_admin)])
async def create_category(cat: CategoryCreate):
    """Create new category"""
    supabase = get_supabase()
    
    result = supabase.table("categories").insert(cat.model_dump()).execute()
    
    if not result.data:
        raise HTTPException(status_code=500, detail="Failed to create category")
    
    logger.info(f"Category created: {cat.name}")
    return Category(**result.data[0])

@router.get("/categories", response_model=List[Category])
async def list_categories():
    """List all categories (accessible to all authenticated users)"""
    supabase = get_supabase()
    
    result = supabase.table("categories").select("*").execute()
    return [Category(**cat) for cat in result.data]

@router.put("/categories/{cat_id}", response_model=Category, dependencies=[Depends(get_current_admin)])
async def update_category(cat_id: str, cat: CategoryCreate):
    """Update category"""
    supabase = get_supabase()
    
    result = supabase.table("categories").update(cat.model_dump()).eq("id", cat_id).execute()
    
    if not result.data:
        raise HTTPException(status_code=404, detail="Category not found")
    
    logger.info(f"Category updated: {cat_id}")
    return Category(**result.data[0])

@router.delete("/categories/{cat_id}", dependencies=[Depends(get_current_admin)])
async def delete_category(cat_id: str):
    """Delete category"""
    supabase = get_supabase()
    
    # Check if category has documents
    docs = supabase.table("document_categories").select("document_id").eq("category_id", cat_id).execute()
    if docs.data:
        raise HTTPException(status_code=400, detail="Cannot delete category with documents")
    
    # Delete user associations
    supabase.table("user_categories").delete().eq("category_id", cat_id).execute()
    
    # Delete category
    result = supabase.table("categories").delete().eq("id", cat_id).execute()
    
    if not result.data:
        raise HTTPException(status_code=404, detail="Category not found")
    
    logger.info(f"Category deleted: {cat_id}")
    return {"message": "Category deleted"}

# Dashboard & Statistics
@router.get("/dashboard", response_model=DashboardStats, dependencies=[Depends(get_current_admin)])
async def get_dashboard_stats():
    """Get dashboard statistics"""
    supabase = get_supabase()
    
    # Total documents
    docs_result = supabase.table("documents").select("id, file_size").execute()
    total_documents = len(docs_result.data)
    storage_used_bytes = sum(doc["file_size"] for doc in docs_result.data)
    storage_used_mb = round(storage_used_bytes / (1024 * 1024), 2)
    
    # Active users
    users_result = supabase.table("users").select("id").eq("is_active", True).execute()
    active_users = len(users_result.data)
    
    # Questions this month
    month_start = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    chats_result = supabase.table("chat_history").select("id").gte("created_at", month_start.isoformat()).execute()
    questions_this_month = len(chats_result.data)
    
    # Knowledge gaps (questions with low confidence)
    gaps_result = supabase.table("chat_history")\
        .select("question, confidence_score, created_at")\
        .lt("confidence_score", 50)\
        .order("created_at", desc=True)\
        .limit(100)\
        .execute()
    
    # Group by question
    question_counts = {}
    for chat in gaps_result.data:
        q = chat["question"]
        if q in question_counts:
            question_counts[q]["count"] += 1
            question_counts[q]["total_confidence"] += chat["confidence_score"]
            if chat["created_at"] > question_counts[q]["last_asked"]:
                question_counts[q]["last_asked"] = chat["created_at"]
        else:
            question_counts[q] = {
                "count": 1,
                "total_confidence": chat["confidence_score"],
                "last_asked": chat["created_at"]
            }
    
    knowledge_gaps = [
        KnowledgeGap(
            question=q,
            count=data["count"],
            last_asked=datetime.fromisoformat(data["last_asked"]),
            avg_confidence=round(data["total_confidence"] / data["count"], 1)
        )
        for q, data in sorted(question_counts.items(), key=lambda x: x[1]["count"], reverse=True)[:10]
    ]
    
    # Department statistics
    depts_result = supabase.table("departments").select("*").execute()
    department_stats = []
    
    for dept in depts_result.data:
        # Get users in department
        dept_users = supabase.table("users").select("id").eq("department_id", dept["id"]).execute()
        user_ids = [u["id"] for u in dept_users.data]
        
        if user_ids:
            # Count questions
            dept_chats = supabase.table("chat_history").select("id").in_("user_id", user_ids).execute()
            question_count = len(dept_chats.data)
            
            # Count documents uploaded by department
            dept_docs = supabase.table("documents").select("id").in_("uploaded_by", user_ids).execute()
            document_count = len(dept_docs.data)
        else:
            question_count = 0
            document_count = 0
        
        department_stats.append(DepartmentStats(
            department_id=dept["id"],
            department_name=dept["name"],
            question_count=question_count,
            document_count=document_count
        ))
    
    return DashboardStats(
        total_documents=total_documents,
        active_users=active_users,
        questions_this_month=questions_this_month,
        storage_used_mb=storage_used_mb,
        knowledge_gaps=knowledge_gaps,
        department_stats=department_stats
    )

# Audit Log
@router.get("/audit-log", response_model=List[AuditLog], dependencies=[Depends(get_current_admin)])
async def get_audit_log(
    limit: int = 100,
    action: str = None,
    user_id: str = None
):
    """Get audit log"""
    supabase = get_supabase()
    
    query = supabase.table("audit_log").select("*")
    
    if action:
        query = query.eq("action", action)
    
    if user_id:
        query = query.eq("user_id", user_id)
    
    result = query.order("created_at", desc=True).limit(limit).execute()
    
    return [AuditLog(**log) for log in result.data]
