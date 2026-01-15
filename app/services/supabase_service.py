"""
Supabase service for backend operations.
Handles database updates after AI processing.
"""
import os
from typing import Optional
from supabase import create_client, Client
from dotenv import load_dotenv
import logging

logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()


class SupabaseService:
    """Service for Supabase database operations"""
    
    _client: Optional[Client] = None
    
    @classmethod
    def get_client(cls) -> Client:
        """Get or create Supabase client instance"""
        if cls._client is None:
            supabase_url = os.getenv("SUPABASE_URL")
            supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
            
            if not supabase_url or not supabase_key:
                raise ValueError(
                    "SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set in environment variables"
                )
            
            cls._client = create_client(supabase_url, supabase_key)
            logger.info("Supabase client initialized successfully")
        
        return cls._client
    
    @classmethod
    def update_case_summary(cls, case_id: str, summary: str) -> bool:
        """
        Update the summary field for a case in Supabase.
        
        Args:
            case_id: UUID of the case
            summary: Markdown summary to save
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            client = cls.get_client()
            
            # Update the case with summary and set processing to false
            # Note: updated_at is automatically managed by Supabase, no need to set it
            result = client.table("cases").update({
                "summary": summary,
                "processing": False
            }).eq("id", case_id).execute()
            
            logger.info(f"Successfully updated summary for case {case_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to update case summary: {e}")
            return False
