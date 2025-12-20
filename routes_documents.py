# routes_documents.py - UPDATED WITH OWNERSHIP

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from typing import List, Optional
from database import get_db
from models import Document, User, DocumentCategory
from auth import get_current_user
import logging

router = APIRouter(prefix="/api/documents", tags=["documents"])
logger = logging.getLogger(__name__)


@router.get("/my-documents")
async def get_my_documents(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get documents uploaded by current user
    Admins see ALL documents, others see only their own
    """
    try:
        if current_user.role == "admin":
            # Admin sees ALL documents
            documents = db.query(Document).all()
        else:
            # Regular users see only their own
            documents = db.query(Document).filter(
                Document.uploaded_by == current_user.id
            ).all()
        
        return {
            "documents": [
                {
                    "id": doc.id,
                    "title": doc.title,
                    "filename": doc.filename,
                    "file_type": doc.file_type,
                    "uploaded_at": doc.uploaded_at.isoformat(),
                    "uploaded_by": doc.uploaded_by,
                    "uploader_email": doc.uploader.email if doc.uploader else None,
                    "categories": [
                        {"id": cat.id, "name": cat.name} 
                        for cat in doc.categories
                    ]
                }
                for doc in documents
            ]
        }
    except Exception as e:
        logger.error(f"Error fetching documents: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{document_id}")
async def get_document(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get single document details
    Users can only access their own documents, admins can access all
    """
    document = db.query(Document).filter(Document.id == document_id).first()
    
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # Permission check
    if current_user.role != "admin" and document.uploaded_by != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to access this document")
    
    return {
        "id": document.id,
        "title": document.title,
        "filename": document.filename,
        "file_type": document.file_type,
        "content": document.content,
        "uploaded_at": document.uploaded_at.isoformat(),
        "uploaded_by": document.uploaded_by,
        "uploader_email": document.uploader.email if document.uploader else None,
        "categories": [
            {"id": cat.id, "name": cat.name} 
            for cat in document.categories
        ]
    }


@router.put("/{document_id}")
async def update_document(
    document_id: int,
    title: Optional[str] = Form(None),
    category_ids: Optional[str] = Form(None),  # Comma-separated IDs
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update document title and/or categories
    Users can only update their own documents, admins can update all
    """
    document = db.query(Document).filter(Document.id == document_id).first()
    
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # Permission check
    if current_user.role != "admin" and document.uploaded_by != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to update this document")
    
    try:
        # Update title if provided
        if title:
            document.title = title
        
        # Update categories if provided
        if category_ids:
            # Parse comma-separated category IDs
            cat_id_list = [int(id.strip()) for id in category_ids.split(",") if id.strip()]
            
            # Clear existing categories
            document.categories.clear()
            
            # Add new categories
            for cat_id in cat_id_list:
                category = db.query(DocumentCategory).filter(
                    DocumentCategory.id == cat_id
                ).first()
                if category:
                    document.categories.append(category)
        
        db.commit()
        db.refresh(document)
        
        return {
            "message": "Document updated successfully",
            "document": {
                "id": document.id,
                "title": document.title,
                "categories": [
                    {"id": cat.id, "name": cat.name} 
                    for cat in document.categories
                ]
            }
        }
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating document: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{document_id}")
async def delete_document(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Delete a document
    Users can only delete their own documents, admins can delete all
    """
    document = db.query(Document).filter(Document.id == document_id).first()
    
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # Permission check
    if current_user.role != "admin" and document.uploaded_by != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to delete this document")
    
    try:
        db.delete(document)
        db.commit()
        
        return {
            "message": "Document deleted successfully",
            "document_id": document_id
        }
    except Exception as e:
        db.rollback()
        logger.error(f"Error deleting document: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    title: str = Form(...),
    category_ids: str = Form(""),  # Comma-separated category IDs
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Upload a new document
    Automatically sets uploaded_by to current user
    """
    try:
        # Read file content
        content = await file.read()
        
        # Create document
        document = Document(
            title=title,
            filename=file.filename,
            file_type=file.content_type,
            content=content,
            uploaded_by=current_user.id  # Track who uploaded it
        )
        
        # Add categories if provided
        if category_ids:
            cat_id_list = [int(id.strip()) for id in category_ids.split(",") if id.strip()]
            for cat_id in cat_id_list:
                category = db.query(DocumentCategory).filter(
                    DocumentCategory.id == cat_id
                ).first()
                if category:
                    document.categories.append(category)
        
        db.add(document)
        db.commit()
        db.refresh(document)
        
        return {
            "message": "Document uploaded successfully",
            "document": {
                "id": document.id,
                "title": document.title,
                "filename": document.filename
            }
        }
    except Exception as e:
        db.rollback()
        logger.error(f"Error uploading document: {e}")
        raise HTTPException(status_code=500, detail=str(e))
