from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    openai_endpoint: str = ""
    openai_key: str = ""
    openai_api_version: str = "2025-04-01-preview"
    openai_chat_deployment: str = "gpt-4.1"
    openai_embed_deployment: str = "text-embedding-3-small"
    
    search_endpoint: str = ""
    search_admin_key: str = ""
    search_index: str = "multimodal-rag-1750033945665"
    
    foundry_endpoint: Optional[str] = None
    foundry_api_key: Optional[str] = None
    
    document_intel_account_url: str = ""
    document_intel_key: str = ""
    
    tenant_id: Optional[str] = None
    api_client_id: Optional[str] = None
    authority: Optional[str] = None
    user_flow: Optional[str] = None
    jwks_uri: Optional[str] = None
    api_audience: Optional[str] = None
    
    enable_token_tracking: bool = True
    azure_region: Optional[str] = None
    azure_subscription_id: Optional[str] = None
    
    azure_tenant_id: Optional[str] = None
    azure_client_id: Optional[str] = None
    azure_client_secret: Optional[str] = None
    
    azure_cosmos_endpoint: Optional[str] = None
    azure_cosmos_database_name: Optional[str] = None
    azure_cosmos_container_name: Optional[str] = None
    azure_cosmos_evaluation_container_name: Optional[str] = None
    azure_cosmos_token_usage_container_name: Optional[str] = None
    
    azure_storage_account_name: Optional[str] = None
    azure_storage_container_name: Optional[str] = None
    
    class Config:
        env_file = ".env"

settings = Settings()
