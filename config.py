from pydantic_settings import BaseSettings
from typing import List

class Settings(BaseSettings):
    # Supabase
    SUPABASE_URL: str
    SUPABASE_KEY: str
    SUPABASE_ANON_KEY: str
    
    # OpenAI
    OPENAI_API_KEY: str
    
    # Backblaze B2
    B2_KEY_ID: str
    B2_APPLICATION_KEY: str
    B2_BUCKET_NAME: str
    B2_ENDPOINT: str
    
    # JWT
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 43200
    
    # API
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:3000"
---

## 💾 COMMIT DE WIJZIGING

**Scroll naar beneden in GitHub editor:**

1. **Commit message**: `fix: add production domains to CORS whitelist`
2. **Klik "Commit changes"**
3. **Railway deploy automatisch!**

---

## ⏱️ WACHT OP DEPLOYMENT

**In Railway dashboard:**
1. Klik op **"Deployments"** tab
2. Je ziet een nieuwe deployment starten
3. Wacht tot het **groen vinkje** verschijnt (2-3 minuten)

---

## 🧪 TEST DIRECT NA DEPLOYMENT

**Open:**
```
https://h2w-frontend-git-main-floris-lindemans-projects.vercel.app/login
    
    # AI Configuration
    OPENAI_MODEL: str = "gpt-4o"
    AI_TEMPERATURE: float = 0.2
    MAX_TOKENS: int = 1000
    CHUNK_SIZE: int = 1500
    CHUNK_OVERLAP: int = 200
    TOP_K_CHUNKS: int = 8
    SIMILARITY_THRESHOLD: float = 0.65
    
    # Environment
    ENVIRONMENT: str = "development"
    
    class Config:
        env_file = ".env"
        case_sensitive = True
    
    @property
    def cors_origins_list(self) -> List[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]

settings = Settings()  # ← LET OP: Deze regel moet HELEMAAL LINKS (0 spaties)
