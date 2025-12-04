from supabase import create_client, Client
from config import settings
import logging

logger = logging.getLogger(__name__)

class SupabaseClient:
    def __init__(self):
        self.client: Client = create_client(
            settings.SUPABASE_URL,
            settings.SUPABASE_KEY
        )
        logger.info("Supabase client initialized")
    
    def get_client(self) -> Client:
        return self.client

# Singleton instance
supabase_client = SupabaseClient()

def get_supabase() -> Client:
    return supabase_client.get_client()
