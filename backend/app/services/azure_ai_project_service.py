"""
Azure AI Project Service for instrumented OpenAI clients with Azure Monitor tracing
Based on the Azure SDK sample for chat completions with Azure AI inference client and Azure Monitor tracing
"""

import logging
import os
from typing import Optional
from urllib.parse import urlparse

from azure.ai.projects import AIProjectClient
from azure.ai.inference import ChatCompletionsClient
from azure.monitor.opentelemetry import configure_azure_monitor
from azure.identity import DefaultAzureCredential

logger = logging.getLogger(__name__)

class AzureAIProjectService:
    """Azure AI Project service for instrumented OpenAI clients with telemetry"""
    
    def __init__(self):
        self.project_client: Optional[AIProjectClient] = None
        self.chat_client: Optional[ChatCompletionsClient] = None
        self.instrumented: bool = False
        
    async def initialize(self):
        """Initialize the Azure AI Project service with telemetry"""
        try:
            logger.info("Initializing Azure AI Project service with telemetry")
            
            connection_string = "InstrumentationKey=80610342-8cae-456a-b236-e7964d8bca79;IngestionEndpoint=https://eastus-8.in.applicationinsights.azure.com/;LiveEndpoint=https://eastus.livediagnostics.monitor.azure.com/;ApplicationId=c635d8b8-9181-4717-89e2-773643eef511"
            configure_azure_monitor(connection_string=connection_string)
            logger.info("Azure Monitor tracing configured")
            
            endpoint = "https://citigkpoc-resource.services.ai.azure.com/api/projects/citigkpoc"
            credential = DefaultAzureCredential()
            
            subscription_id = "placeholder-subscription-id"
            resource_group_name = "placeholder-resource-group"
            project_name = "citigkpoc"
            
            try:
                self.project_client = AIProjectClient(
                    subscription_id=subscription_id,
                    resource_group_name=resource_group_name,
                    project_name=project_name,
                    credential=credential
                )
                logger.info(f"Project client initialized for project: {project_name}")
            except Exception as e:
                logger.warning(f"AIProjectClient initialization failed: {e}")
                self.project_client = None
            
            inference_endpoint = f"https://{urlparse(endpoint).netloc}/models"
            self.chat_client = ChatCompletionsClient(
                endpoint=inference_endpoint,
                credential=credential,
                credential_scopes=["https://ai.azure.com/.default"]
            )
            logger.info(f"Chat completions client initialized with endpoint: {inference_endpoint}")
            
            self.instrumented = True
            logger.info("Azure AI Project service initialized successfully with telemetry")
            
        except Exception as e:
            logger.error(f"Failed to initialize Azure AI Project service: {e}")
            self.instrumented = False
            raise
    
    def get_chat_client(self) -> Optional[ChatCompletionsClient]:
        """Get the instrumented chat client"""
        if not self.instrumented:
            logger.warning("Azure AI Project service not properly initialized")
            return None
        return self.chat_client
    
    def get_project_client(self) -> Optional[AIProjectClient]:
        """Get the project client"""
        if not self.instrumented:
            logger.warning("Azure AI Project service not properly initialized")
            return None
        return self.project_client
    
    def is_instrumented(self) -> bool:
        """Check if the service is properly instrumented"""
        return self.instrumented

# Global instance
azure_ai_project_service = AzureAIProjectService()
