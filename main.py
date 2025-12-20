from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from config import settings
import logging

# Import routers
from routes_auth import router as auth_router
from routes_users import router as users_router
from routes_documents import router as documents_router
from routes_chat import router as chat_router
from routes_admin import router as admin_router
from routes_categories import router as categories_router

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="AI Knowledge Base API",
    description="Enterprise knowledge base with AI-powered search",
    version="1.0.0"
)

# Configure CORS - EXPLICIT ORIGINS FOR SECURITY
origins = [
    "http://localhost:3000",
    "http://localhost:5173",
    "https://h2w-frontend.vercel.app",
    "https://h2wchatbot-production.up.railway.app",
    "https://ncg.3xai.nl",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,  # Use explicit list instead of settings
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth_router, prefix="/api")
app.include_router(users_router, prefix="/api")
app.include_router(documents_router, prefix="/api")
app.include_router(chat_router, prefix="/api")
app.include_router(admin_router, prefix="/api")
app.include_router(categories_router, prefix="/api")

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "AI Knowledge Base API",
        "version": "1.0.0",
        "status": "operational"
    }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=settings.ENVIRONMENT == "development"
    )
