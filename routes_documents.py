from fastapi import APIRouter, HTTPException, status, Depends, UploadFile, File, Form
from typing import List, Optional
from models import Document, DocumentCreate, DocumentUpdate, DocumentWithCategories, TagSuggestionRequest
from auth import get_current_user, get_current_admin, TokenData
from database import get_supabase
from storage import get_storage
from document_processor import get_document_processor
from openai_service import get_openai_service
import logging
import json
from datetime import datetime

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/documents", tags=["Documents"])

@router.post("/upload", response_model=DocumentWithCategories)
async def upload_document(
    file: UploadFile = File(...),
    title: str = Form(...),
    category_ids: Optional[str] = Form("[]"),
    tags: Optional[str] = Form("[]"),
    expiry_date: Optional[str] = Form(None),
    current_user: TokenData = Depends(get_current_user)
):
    """Upload a document"""
    supabase = get_supabase()
    storage = get_storage()
    processor = get_document_processor()
    openai_svc = get_openai_service()
    
    # Parse JSON strings with better error handling
    try:
        if not category_ids or category_ids == "null" or category_ids.strip() == "":
            category_list = []
        else:
            category_list = json.loads(category_ids)
        
        if not tags or tags == "null" or tags.strip() == "":
            tags_list = []
        else:
            tags_list = json.loads(tags)
    except (json.JSONDecodeError, AttributeError) as e:
        logger.error(f"JSON parse error: {e}, category_ids={category_ids}, tags={tags}")
        category_list = []
        tags_list = []
    
    # Validate user has access to these categories
    if category_list:
        user_cats = supabase.table("user_categories").select("category_id").eq("user_id", current_user.user_id).execute()
        user_category_ids = [item["category_id"] for item in user_cats.data]
        
        for cat_id in category_list:
            if cat_id not in user_category_ids and current_user.role != "admin":
                raise HTTPException(status_code=403, detail=f"No access to category {cat_id}")
    
    # Get file extension
    file_extension = file.filename.split('.')[-1].lower()
    
    # Read file content
    file_content = await file.read()
    file_size = len(file_content)
    
    # Upload to B2
    try:
        file_url = storage.upload_file(file_content, file.filename, file.content_type)
    except Exception as e:
        logger.error(f"Failed to upload file: {e}")
        raise HTTPException(status_code=500, detail="Failed to upload file")
    
    # Extract text
    extracted_text = processor.process_document(file_content, file_extension)
    
    # Create document record
    doc_data = {
        "title": title,
        "file_name": file.filename,
        "file_type": file_extension,
        "file_url": file_url,
        "file_size": file_size,
        "content_text": extracted_text,
        "uploaded_by": current_user.user_id,
        "tags": tags_list,
        "expiry_date": expiry_date if expiry_date else None,
        "is_expired": False
    }
    
    doc_result = supabase.table("documents").insert(doc_data).execute()
    
    if not doc_result.data:
        raise HTTPException(status_code=500, detail="Failed to create document")
    
    document_id = doc_result.data[0]["id"]
    
    # Associate with categories
    if category_list:
        category_assignments = [
            {"document_id": document_id, "category_id": cat_id}
            for cat_id in category_list
        ]
        supabase.table("document_categories").insert(category_assignments).execute()
    
    # Generate embeddings in background
    try:
        chunks = processor.chunk_text(extracted_text, chunk_size=1000)
        
        for i, chunk in enumerate(chunks):
            embedding = openai_svc.generate_embedding(chunk)
            
            supabase.table("document_embeddings").insert({
                "document_id": document_id,
                "chunk_text": chunk,
                "embedding": embedding,
                "chunk_index": i
            }).execute()
        
        logger.info(f"Generated {len(chunks)} embeddings for document {document_id}")
    except Exception as e:
        logger.error(f"Failed to generate embeddings: {e}")
    
    # Log audit
    supabase.table("audit_log").insert({
        "user_id": current_user.user_id,
        "action": "upload",
        "document_id": document_id,
        "details": {"filename": file.filename, "size": file_size}
    }).execute()
    
    # Get categories for response
    cat_result = supabase.table("categories").select("*").in_("id", category_list).execute() if category_list else type('obj', (object,), {'data': []})()
    
    return DocumentWithCategories(
        **doc_result.data[0],
        categories=cat_result.data,
        uploader_name=current_user.email
    )

@router.post("/suggest-tags", response_model=List[str])
async def suggest_tags(
    request: TagSuggestionRequest,
    current_user: TokenData = Depends(get_current_user)
):
    """Generate tag suggestions for a document"""
    openai_svc = get_openai_service()
    
    try:
        tags = openai_svc.suggest_tags(request.filename, request.content_preview)
        return tags
    except Exception as e:
        logger.error(f"Failed to generate tags: {e}")
        return []

@router.get("/", response_model=List[DocumentWithCategories])
async def list_documents(
    category_ids: Optional[str] = None,
    file_types: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    current_user: TokenData = Depends(get_current_user)
):
    """List documents accessible to current user"""
    supabase = get_supabase()
    
    # Get user's accessible categories
    if current_user.role == "admin":
        query = supabase.table("documents").select("*")
    else:
        user_cats = supabase.table("user_categories").select("category_id").eq("user_id", current_user.user_id).execute()
        user_category_ids = [item["category_id"] for item in user_cats.data]
        
        doc_cats = supabase.table("document_categories").select("document_id").in_("category_id", user_category_ids).execute()
        doc_ids = list(set([item["document_id"] for item in doc_cats.data]))
        
        if not doc_ids:
            return []
        
        query = supabase.table("documents").select("*").in_("id", doc_ids)
    
    # Apply filters
    if file_types:
        file_types_list = file_types.split(',')
        query = query.in_("file_type", file_types_list)
    
    if start_date:
        query = query.gte("upload_date", start_date)
    
    if end_date:
        query = query.lte("upload_date", end_date)
    
    result = query.execute()
    
    # Enrich with categories and uploader
    documents = []
    for doc in result.data:
        cat_result = supabase.table("document_categories").select("category_id").eq("document_id", doc["id"]).execute()
        category_ids_list = [item["category_id"] for item in cat_result.data]
        
        cats = supabase.table("categories").select("*").in_("id", category_ids_list).execute() if category_ids_list else type('obj', (object,), {'data': []})()
        
        uploader = supabase.table("users").select("full_name").eq("id", doc["uploaded_by"]).execute()
        uploader_name = uploader.data[0]["full_name"] if uploader.data else "Unknown"
        
        if category_ids:
            filter_cats = category_ids.split(',')
            if not any(cat_id in category_ids_list for cat_id in filter_cats):
                continue
        
        documents.append(DocumentWithCategories(
            **doc,
            categories=cats.data,
            uploader_name=uploader_name
        ))
    
    return documents

@router.get("/my-documents", response_model=List[DocumentWithCategories])
async def get_my_documents(
    current_user: TokenData = Depends(get_current_user)
):
    """Get documents uploaded by current user"""
    supabase = get_supabase()
    
    # Get documents uploaded by this user
    query = supabase.table("documents").select("*").eq("uploaded_by", current_user.user_id)
    result = query.execute()
    
    # Enrich with categories
    documents = []
    for doc in result.data:
        cat_result = supabase.table("document_categories").select("category_id").eq("document_id", doc["id"]).execute()
        category_ids_list = [item["category_id"] for item in cat_result.data]
        
        cats = supabase.table("categories").select("*").in_("id", category_ids_list).execute() if category_ids_list else type('obj', (object,), {'data': []})()
        
        documents.append(DocumentWithCategories(
            **doc,
            categories=cats.data,
            uploader_name=current_user.email
        ))
    
    return documents

@router.get("/{document_id}", response_model=DocumentWithCategories)
async def get_document(
    document_id: str,
    current_user: TokenData = Depends(get_current_user)
):
    """Get specific document"""
    supabase = get_supabase()
    
    if current_user.role != "admin":
        user_cats = supabase.table("user_categories").select("category_id").eq("user_id", current_user.user_id).execute()
        user_category_ids = [item["category_id"] for item in user_cats.data]
        
        doc_cats = supabase.table("document_categories").select("category_id").eq("document_id", document_id).execute()
        doc_category_ids = [item["category_id"] for item in doc_cats.data]
        
        if not any(cat_id in user_category_ids for cat_id in doc_category_ids):
            raise HTTPException(status_code=403, detail="No access to this document")
    
    result = supabase.table("documents").select("*").eq("id", document_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Document not found")
    
    doc = result.data[0]
    
    cat_result = supabase.table("document_categories").select("category_id").eq("document_id", document_id).execute()
    category_ids_list = [item["category_id"] for item in cat_result.data]
    cats = supabase.table("categories").select("*").in_("id", category_ids_list).execute() if category_ids_list else type('obj', (object,), {'data': []})()
    
    uploader = supabase.table("users").select("full_name").eq("id", doc["uploaded_by"]).execute()
    uploader_name = uploader.data[0]["full_name"] if uploader.data else "Unknown"
    
    supabase.table("audit_log").insert({
        "user_id": current_user.user_id,
        "action": "view",
        "document_id": document_id
    }).execute()
    
    return DocumentWithCategories(
        **doc,
        categories=cats.data,
        uploader_name=uploader_name
    )

@router.delete("/{document_id}")
async def delete_document(
    document_id: str,
    current_user: TokenData = Depends(get_current_user)
):
    """Delete document"""
    supabase = get_supabase()
    storage = get_storage()
    
    doc_result = supabase.table("documents").select("*").eq("id", document_id).execute()
    if not doc_result.data:
        raise HTTPException(status_code=404, detail="Document not found")
    
    doc = doc_result.data[0]
    
    if doc["uploaded_by"] != current_user.user_id and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="No permission to delete this document")
    
    try:
        storage.delete_file(doc["file_url"])
    except Exception as e:
        logger.error(f"Failed to delete file from storage: {e}")
    
    supabase.table("document_embeddings").delete().eq("document_id", document_id).execute()
    supabase.table("document_categories").delete().eq("document_id", document_id).execute()
    supabase.table("documents").delete().eq("id", document_id).execute()
    
    supabase.table("audit_log").insert({
        "user_id": current_user.user_id,
        "action": "delete",
        "document_id": document_id,
        "details": {"filename": doc["file_name"]}
    }).execute()
    
    logger.info(f"Document deleted: {document_id}")
    return {"message": "Document deleted successfully"}
