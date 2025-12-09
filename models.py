from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, EmailStr
from enum import Enum

class UserRole(str, Enum):
    ADMIN = "admin"
    MANAGER = "manager"
    MEDEWERKER = "medewerker"

class ActionType(str, Enum):
    UPLOAD = "upload"
    DELETE = "delete"
    VIEW = "view"
    DOWNLOAD = "download"

# User Models
class UserBase(BaseModel):
    email: EmailStr
    full_name: str
    role: UserRole
    department_id: Optional[str] = None
    is_active: bool = True

class UserCreate(UserBase):
    password: str
    category_ids: List[str] = []

class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    role: Optional[UserRole] = None
    department_id: Optional[str] = None
    is_active: Optional[bool] = None
    category_ids: Optional[List[str]] = None

class User(UserBase):
    id: str
    created_at: datetime
    
    class Config:
        from_attributes = True

class UserWithCategories(User):
    categories: List[str] = []

# Department Models
class DepartmentBase(BaseModel):
    name: str
    description: Optional[str] = None

class DepartmentCreate(DepartmentBase):
    pass

class Department(DepartmentBase):
    id: str
    created_at: datetime
    
    class Config:
        from_attributes = True

# Category Models
class CategoryBase(BaseModel):
    name: str
    description: Optional[str] = None
    color: str = "#2563eb"
    icon: str = "folder"

class CategoryCreate(CategoryBase):
    pass

class Category(CategoryBase):
    id: str
    created_at: datetime
    
    class Config:
        from_attributes = True

# Document Models
class DocumentBase(BaseModel):
    title: str
    file_type: str
    tags: List[str] = []
    expiry_date: Optional[datetime] = None

class DocumentCreate(DocumentBase):
    file_name: str
    file_url: str
    file_size: int
    category_ids: List[str]

class DocumentUpdate(BaseModel):
    title: Optional[str] = None
    tags: Optional[List[str]] = None
    expiry_date: Optional[datetime] = None
    category_ids: Optional[List[str]] = None

class Document(DocumentBase):
    id: str
    file_name: str
    file_url: str
    file_size: int
    uploaded_by: str
    upload_date: datetime
    is_expired: bool
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

class DocumentWithCategories(Document):
    categories: List[Category] = []
    uploader_name: Optional[str] = None

# Chat Models
class ChatQuestion(BaseModel):
    question: str
    category_filters: Optional[List[str]] = None
    date_filter_start: Optional[datetime] = None
    date_filter_end: Optional[datetime] = None
    file_type_filters: Optional[List[str]] = None

class SourceDocument(BaseModel):
    document_id: str
    document_title: str
    document_url: str
    file_type: str

class ChatResponse(BaseModel):
    answer: str
    confidence: float
    sources: List[SourceDocument]

class ChatHistory(BaseModel):
    id: str
    user_id: str
    question: str
    answer: str
    confidence_score: float
    source_documents: List[SourceDocument]
    feedback: Optional[int] = None
    created_at: datetime
    
    class Config:
        from_attributes = True

class ChatFeedback(BaseModel):
    feedback: int  # 1 for thumbs up, -1 for thumbs down

# Auth Models
class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    email: str
    role: str

class TokenData(BaseModel):
    user_id: str
    email: str
    role: UserRole

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

# Audit Log Models
class AuditLog(BaseModel):
    id: str
    user_id: str
    action: ActionType
    document_id: Optional[str] = None
    details: Optional[dict] = None
    created_at: datetime
    
    class Config:
        from_attributes = True

# Statistics Models
class DepartmentStats(BaseModel):
    department_id: str
    department_name: str
    question_count: int
    document_count: int

class KnowledgeGap(BaseModel):
    question: str
    count: int
    last_asked: datetime
    avg_confidence: float

class DashboardStats(BaseModel):
    total_documents: int
    active_users: int
    questions_this_month: int
    storage_used_mb: float
    knowledge_gaps: List[KnowledgeGap]
    department_stats: List[DepartmentStats]

# Tag suggestion request
class TagSuggestionRequest(BaseModel):
    filename: str
    content_preview: Optional[str] = None
