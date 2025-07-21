from pydantic_settings import BaseSettings
from typing import Optional
import os

class Settings(BaseSettings):   
    openai_endpoint: str = os.getenv("OPENAI_ENDPOINT", "")
    openai_key: str = os.getenv("OPENAI_API_KEY", "")
    openai_api_version: str = os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-01")
    openai_chat_deployment: str = os.getenv("OPENAI_CHAT_DEPLOYMENT", "chat4omini")
    openai_embed_deployment: str = os.getenv("OPENAI_EMBED_DEPLOYMENT", "text-embedding-3-small")

    search_endpoint: str = os.getenv("SEARCH_ENDPOINT", "")
    search_index: str = os.getenv("SEARCH_INDEX", "adaptive-rag")
    search_index_upload: str = os.getenv("SEARCH_INDEX_UPLOAD", "adaptive-rag-upload")
    search_admin_key: str = os.getenv("SEARCH_ADMIN_KEY", "")
    
    foundry_endpoint: Optional[str] = None
    foundry_api_key: Optional[str] = None
    
    document_intel_account_url: str = os.getenv("DOCUMENT_INTEL_ACCOUNT_URL", "")
    document_intel_key: str = os.getenv("DOCUMENT_INTEL_KEY", "")
        
    tenant_id: Optional[str] = None
    api_client_id: Optional[str] = None
    authority: Optional[str] = None
    user_flow: Optional[str] = None
    jwks_uri: Optional[str] = None
    api_audience: Optional[str] = None
    
    enable_token_tracking: bool = True
    azure_region: Optional[str] = None
    azure_subscription_id: Optional[str] = None
    
    azure_tenant_id: Optional[str] = os.getenv("AZURE_TENANT_ID", "")
    azure_client_id: Optional[str] = os.getenv("AZURE_CLIENT_ID", "")
    azure_client_secret: Optional[str] = os.getenv("AZURE_CLIENT_SECRET", "")
    
    azure_cosmos_endpoint: str = os.getenv("AZURE_COSMOS_ENDPOINT", "")
    azure_cosmos_database_name: str = os.getenv("AZURE_COSMOS_DATABASE_NAME", "rag-financial-db")
    azure_cosmos_container_name: str = os.getenv("AZURE_COSMOS_CONTAINER_NAME", "chat-sessions")
    azure_cosmos_evaluation_container_name: str = os.getenv("AZURE_COSMOS_EVALUATION_CONTAINER_NAME", "evaluation-results")
    azure_cosmos_token_usage_container_name: str = os.getenv("AZURE_COSMOS_TOKEN_USAGE_CONTAINER_NAME", "token-usage")
    azure_cosmos_key: str = os.getenv("AZURE_COSMOS_KEY", "")
    
    azure_storage_account_name: Optional[str] = None
    azure_storage_container_name: Optional[str] = None
    
    max_document_size_mb: int = int(os.getenv("MAX_DOCUMENT_SIZE_MB", "50"))
    supported_document_types: str = os.getenv("SUPPORTED_DOCUMENT_TYPES", "pdf,docx,xlsx,txt")
    chunk_size: int = int(os.getenv("CHUNK_SIZE", "1000"))
    chunk_overlap: int = int(os.getenv("CHUNK_OVERLAP", "200"))
    max_chunks_per_document: int = int(os.getenv("MAX_CHUNKS_PER_DOCUMENT", "500"))

    class Config:
        env_file = ".env"

settings = Settings()
