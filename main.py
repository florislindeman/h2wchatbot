from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
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

# Use CORS origins from environment variable
origins = settings.cors_origins_list

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ✅ CRITICAL: Exception handlers to ensure CORS headers are ALWAYS present

@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """Handle HTTP exceptions with CORS headers"""
    origin = request.headers.get("origin")
    
    headers = {}
    if origin in origins:
        headers.update({
            "Access-Control-Allow-Origin": origin,
            "Access-Control-Allow-Credentials": "true",
            "Access-Control-Allow-Methods": "*",
            "Access-Control-Allow-Headers": "*",
        })
    
    logger.warning(f"HTTP {exc.status_code}: {exc.detail}")
    
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
        headers=headers
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle validation errors with CORS headers"""
    origin = request.headers.get("origin")
    
    headers = {}
    if origin in origins:
        headers.update({
            "Access-Control-Allow-Origin": origin,
            "Access-Control-Allow-Credentials": "true",
        })
    
    logger.warning(f"Validation error: {exc.errors()}")
    
    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors()},
        headers=headers
    )

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Handle all unhandled exceptions with CORS headers"""
    origin = request.headers.get("origin")
    
    headers = {}
    if origin in origins:
        headers.update({
            "Access-Control-Allow-Origin": origin,
            "Access-Control-Allow-Credentials": "true",
            "Access-Control-Allow-Methods": "*",
            "Access-Control-Allow-Headers": "*",
        })
    
    # Log the full exception
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    
    # Return user-friendly error with CORS headers
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal server error occurred",
            "error_type": type(exc).__name__,
            "error_message": str(exc)
        },
        headers=headers
    )

# Include routers
app.include_router(auth_router)
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
