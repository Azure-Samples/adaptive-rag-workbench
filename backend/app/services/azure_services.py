from azure.search.documents import SearchClient
from azure.search.documents.aio import SearchClient as AsyncSearchClient
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.models import VectorizedQuery
try:
    from azure.ai.documentintelligence import DocumentIntelligenceClient
except ImportError:
    # Fallback for missing document intelligence module
    DocumentIntelligenceClient = None
try:
    from azure.cosmos import CosmosClient
except ImportError:
    # Fallback for missing cosmos module
    CosmosClient = None
from azure.identity import DefaultAzureCredential, ClientSecretCredential
from azure.core.credentials import AzureKeyCredential
from openai import AzureOpenAI, AsyncAzureOpenAI
import asyncio
import logging
import os
import platform
import random
import traceback
import uuid
from typing import List, Dict, Any, Optional, Union
from datetime import datetime, date
import hashlib
import json
from dataclasses import dataclass
import time

# Configure Windows event loop policy for Azure SDK compatibility
if platform.system() == "Windows":
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    except Exception:
        pass

from ..core.config import settings

logger = logging.getLogger(__name__)

class MockSearchClient:
    def __init__(self):
        self.documents = []
    
    def upload_documents(self, documents):
        self.documents.extend(documents)
        return {"status": "success", "count": len(documents)}
    
    def search(self, search_text=None, vector_queries=None, **kwargs):
        return [
            {
                "id": "mock-doc-1",
                "content": "Sample financial content from 10-K report",
                "title": "Sample Financial Corporation 10-K",
                "document_type": "10-K",
                "company": "Sample Financial Corporation",
                "filing_date": "2023-12-31",
                "source": "mock://sample-10k.pdf",
                "credibility_score": 0.95
            }
        ]

class MockSearchIndexClient:
    def create_or_update_index(self, index):
        return {"status": "success", "name": index.name}
    
    def delete_index(self, index_name):
        return {"status": "success", "deleted": index_name}
    
    def get_index(self, index_name):
        from azure.search.documents.indexes.models import SearchIndex, SimpleField, SearchFieldDataType
        return SearchIndex(
            name=index_name,
            fields=[SimpleField(name="id", type=SearchFieldDataType.String, key=True)]
        )

class MockDocumentIntelligenceClient:
    def begin_analyze_document(self, model_id, body, content_type="application/pdf"):
        class MockPoller:
            def result(self):
                class MockResult:
                    def __init__(self):
                        self.content = "Mock extracted content from financial document"
                        self.pages = [{"page_number": 1}]
                        self.tables = []
                        self.key_value_pairs = []
                return MockResult()
        return MockPoller()

class MockOpenAIClient:
    def __init__(self):
        self.embeddings = MockEmbeddings()

class MockEmbeddings:
    def create(self, input, model):
        class MockResponse:
            def __init__(self):
                self.data = [MockEmbeddingData()]
        return MockResponse()

class MockEmbeddingData:
    def __init__(self):
        import random
        self.embedding = [random.random() for _ in range(1536)]

class AzureServiceManager:
    def __init__(self):
        self.search_client = None
        self.search_client_upload = None
        self.async_search_client = None
        self.search_index_client = None
        self.form_recognizer_client = None
        self.openai_client = None
        self.async_openai_client = None
        self.cosmos_client = None
        self.credential = None
        self._use_mock = os.getenv("MOCK_AZURE_SERVICES", "false").lower() == "true"
        
    async def initialize(self):
        """Initialize all Azure services"""
        try:
            if self._use_mock:
                logger.info("Initializing mock Azure services for development...")
                await self._initialize_mock_services()
                return
            
            logger.info("Initializing real Azure services...")
            
            # Initialize credentials
            if settings.search_admin_key:
                # Use API key authentication if available
                self.search_credential = AzureKeyCredential(settings.search_admin_key)
                logger.info("Using API key authentication for Azure Search")
            elif settings.azure_client_secret and settings.azure_tenant_id and settings.azure_client_id:
                # Use Service Principal authentication
                self.credential = ClientSecretCredential(
                    tenant_id=settings.azure_tenant_id,
                    client_id=settings.azure_client_id,
                    client_secret=settings.azure_client_secret
                )
                self.search_credential = self.credential
                logger.info("Using Service Principal authentication")
            else:
                # Use default Azure credential
                self.credential = DefaultAzureCredential()
                self.search_credential = self.credential
                logger.info("Using Default Azure Credential")
            
            # Initialize Azure Search clients
            search_endpoint = settings.search_endpoint
            
            self.search_client = SearchClient(
                endpoint=search_endpoint,
                index_name=settings.search_index,
                credential=self.search_credential
            )

            self.search_client_upload = SearchClient(
                endpoint=search_endpoint,
                index_name=settings.search_index_upload,
                credential=self.search_credential
            )
            
            self.async_search_client = AsyncSearchClient(
                endpoint=search_endpoint,
                index_name=settings.search_index,
                credential=self.search_credential
            )
            
            self.search_index_client = SearchIndexClient(
                endpoint=search_endpoint,
                credential=self.search_credential
            )
            
            # Initialize Document Intelligence client
            if hasattr(settings, 'document_intel_account_url') and settings.document_intel_account_url:
                if isinstance(self.search_credential, AzureKeyCredential):
                    # For API key auth, we need a separate DI key
                    di_credential = AzureKeyCredential(getattr(settings, 'document_intel_key', ''))
                else:
                    di_credential = self.credential
                
                self.form_recognizer_client = DocumentIntelligenceClient(
                    endpoint=settings.document_intel_account_url,
                    credential=di_credential
                )
                logger.info("Document Intelligence client initialized")
            else:
                logger.warning("Document Intelligence endpoint not configured")
                self.form_recognizer_client = None
            
            # Initialize Azure OpenAI clients directly (not using Azure AI Project service for now)
            # The Azure AI Project service returns ChatCompletionsClient which doesn't have embeddings
            if hasattr(settings, 'openai_endpoint') and settings.openai_endpoint:
                self.openai_client = AzureOpenAI(
                    azure_endpoint=settings.openai_endpoint,
                    api_key=settings.openai_key,
                    api_version=settings.openai_api_version
                )
                
                self.async_openai_client = AsyncAzureOpenAI(
                    azure_endpoint=settings.openai_endpoint,
                    api_key=settings.openai_key,
                    api_version=settings.openai_api_version
                )
                logger.info(f"Azure OpenAI clients initialized with API version {settings.openai_api_version}")
                
                # Initialize Azure AI Project service for chat telemetry (optional)
                try:
                    from .azure_ai_project_service import azure_ai_project_service
                    await azure_ai_project_service.initialize()
                    
                    if azure_ai_project_service.is_instrumented():
                        # Keep the chat client separate for telemetry, but use regular OpenAI for embeddings
                        self.chat_client = azure_ai_project_service.get_chat_client()
                        logger.info("Azure AI Project chat client initialized with telemetry")
                    else:
                        logger.info("Azure AI Project service not instrumented, using regular OpenAI only")
                        
                except Exception as e:
                    logger.warning(f"Failed to initialize Azure AI Project service: {e}")
                    logger.info("Using regular OpenAI clients only")
            else:
                logger.warning("Azure OpenAI endpoint not configured")
                self.openai_client = None
                self.async_openai_client = None
            
            # Initialize CosmosDB client
            if hasattr(settings, 'azure_cosmos_endpoint') and settings.azure_cosmos_endpoint:
                if CosmosClient is None:
                    logger.warning("CosmosDB client not available - azure-cosmos package not installed")
                    self.cosmos_client = None
                else:
                    logger.info(f"Initializing CosmosDB client with endpoint: {settings.azure_cosmos_endpoint}")
                    try:
                        # Check if we have service principal credentials
                        if (hasattr(settings, 'azure_tenant_id') and settings.azure_tenant_id and
                            hasattr(settings, 'azure_client_id') and settings.azure_client_id and
                            hasattr(settings, 'azure_client_secret') and settings.azure_client_secret):
                            logger.info("Using Service Principal authentication for CosmosDB")
                            cosmos_credential = ClientSecretCredential(
                                tenant_id=settings.azure_tenant_id,
                                client_id=settings.azure_client_id,
                                client_secret=settings.azure_client_secret
                            )
                        elif hasattr(settings, 'azure_cosmos_key') and settings.azure_cosmos_key:
                            logger.info("Using CosmosDB key for authentication")
                            cosmos_credential = settings.azure_cosmos_key
                        elif self.credential:
                            logger.info("Using existing Azure credential for CosmosDB authentication")
                            cosmos_credential = self.credential
                        else:
                            logger.warning("No suitable CosmosDB authentication method found")
                            self.cosmos_client = None
                            return
                        
                        self.cosmos_client = CosmosClient(
                            url=settings.azure_cosmos_endpoint,
                            credential=cosmos_credential
                        )
                        
                        if self.cosmos_client:
                            logger.info("CosmosDB client initialized successfully")
                            # Test the connection by listing databases
                            try:
                                list(self.cosmos_client.list_databases())
                                logger.info("CosmosDB connection test successful")
                            except Exception as test_e:
                                logger.warning(f"CosmosDB connection test failed: {test_e}")
                        
                    except Exception as e:
                        logger.error(f"Failed to initialize CosmosDB client: {e}")
                        import traceback
                        logger.error(f"CosmosDB initialization error details: {traceback.format_exc()}")
                        self.cosmos_client = None
            else:
                logger.warning("CosmosDB endpoint not configured - session storage will be disabled")
                self.cosmos_client = None
            
            # Ensure search index exists
            await self.ensure_search_index_exists()
            
            logger.info("Azure services initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize Azure services: {e}")
            logger.info("Falling back to mock services...")
            await self._initialize_mock_services()
    
    async def _initialize_mock_services(self):
        """Initialize mock services for local development"""
        self.search_client = MockSearchClient()
        self.async_search_client = MockSearchClient()
        self.search_index_client = MockSearchIndexClient()
        self.form_recognizer_client = MockDocumentIntelligenceClient()
        self.openai_client = MockOpenAIClient()
        self.async_openai_client = MockOpenAIClient()
        self.cosmos_client = None  # Mock CosmosDB not needed for basic functionality
        self.credential = None
        self._use_mock = True
        
        logger.info("Mock Azure services initialized for local development")
    
    async def cleanup(self):
        """Cleanup resources"""
        try:
            if hasattr(self, 'async_openai_client') and self.async_openai_client and not self._use_mock:
                if hasattr(self.async_openai_client, 'close'):
                    await self.async_openai_client.close()
                    
            if hasattr(self, 'async_search_client') and self.async_search_client and not self._use_mock:
                if hasattr(self.async_search_client, 'close'):
                    await self.async_search_client.close()
                    
            logger.info("Azure services cleaned up")
        except Exception as e:
            logger.error(f"Error during Azure services cleanup: {e}")
    
    async def _ensure_search_index_exists(self) -> bool:
        """Ensure the search index exists, create it if it doesn't"""
        try:
            if self._use_mock:
                logger.info("Using mock services - skipping index creation")
                return True
                
            logger.info(f"Checking if search index '{settings.search_index}' exists")
            
            # Check if index exists
            try:
                index = self.search_index_client.get_index(settings.search_index)
                logger.info(f"Search index '{settings.search_index}' already exists with {len(index.fields)} fields")
                return True
            except Exception as e:
                logger.info(f"Search index '{settings.search_index}' does not exist, creating it. Error: {e}")
                
            # Create the index with enhanced schema
            index = await self._create_enhanced_search_index()
            result = self.search_index_client.create_index(index)
            logger.info(f"Successfully created search index '{settings.search_index}'")
            return True
            
        except Exception as e:
            logger.error(f"Failed to ensure search index exists: {e}")
            return False
    
    async def create_search_index(self):
        """
        DEPRECATED: Use ensure_search_index_exists() instead.
        This method is kept for backward compatibility but will call ensure_search_index_exists().
        """
        logger.warning("create_search_index() is deprecated. Use ensure_search_index_exists() instead.")
        return await self.ensure_search_index_exists()

    async def ensure_search_index_exists(self) -> bool:
        """Ensure the search index exists, create it if it doesn't"""
        try:
            logger.info(f"Checking if search index '{settings.search_index}' exists")
            
            # Check if index exists
            try:
                existing_index = self.search_index_client.get_index(settings.search_index)
                logger.info(f"Search index '{settings.search_index}' already exists with {len(existing_index.fields)} fields")
                
                # Check if the index schema needs updating for facetable fields
                needs_update = self._check_if_index_needs_facetable_update(existing_index)
                
                if needs_update:
                    logger.info("Index schema needs updating for facetable fields. Recreating index...")
                    # Delete the existing index
                    self.search_index_client.delete_index(settings.search_index)
                    logger.info(f"Deleted existing index '{settings.search_index}' for schema update")
                    # Continue to create the new index
                else:
                    return True
                    
            except Exception as e:
                logger.info(f"Search index '{settings.search_index}' does not exist, creating it. Error: {e}")

            # Create the index
            from azure.search.documents.indexes.models import (
                SearchIndex, SearchField, SearchFieldDataType, SimpleField, 
                SearchableField, VectorSearch, HnswAlgorithmConfiguration,
                VectorSearchProfile, SemanticConfiguration, SemanticPrioritizedFields,
                SemanticField, SemanticSearch
            )
            fields = [
                SimpleField(name="id", type=SearchFieldDataType.String, key=True),
                SearchableField(name="content", type=SearchFieldDataType.String),
                SearchableField(name="title", type=SearchFieldDataType.String),
                SimpleField(name="document_id", type=SearchFieldDataType.String, filterable=True),
                SimpleField(name="source", type=SearchFieldDataType.String, filterable=True, facetable=True),
                SimpleField(name="chunk_id", type=SearchFieldDataType.String, filterable=True),
                SimpleField(name="document_type", type=SearchFieldDataType.String, filterable=True, facetable=True),
                SimpleField(name="company", type=SearchFieldDataType.String, filterable=True, facetable=True),
                SimpleField(name="filing_date", type=SearchFieldDataType.String, filterable=True, facetable=True),
                SimpleField(name="section_type", type=SearchFieldDataType.String, filterable=True, facetable=True),
                SimpleField(name="page_number", type=SearchFieldDataType.Int32, filterable=True),
                SimpleField(name="credibility_score", type=SearchFieldDataType.Double, filterable=True),
                SimpleField(name="processed_at", type=SearchFieldDataType.String, filterable=True),
                SimpleField(name="citation_info", type=SearchFieldDataType.String),
                # SEC-specific fields from Edgar tools
                SimpleField(name="ticker", type=SearchFieldDataType.String, filterable=True, facetable=True),
                SimpleField(name="cik", type=SearchFieldDataType.String, filterable=True),
                SimpleField(name="industry", type=SearchFieldDataType.String, filterable=True, facetable=True),
                SimpleField(name="sic", type=SearchFieldDataType.String, filterable=True),
                SimpleField(name="entity_type", type=SearchFieldDataType.String, filterable=True, facetable=True),
                SimpleField(name="form_type", type=SearchFieldDataType.String, filterable=True, facetable=True),
                SimpleField(name="accession_number", type=SearchFieldDataType.String, filterable=True),
                SimpleField(name="period_end_date", type=SearchFieldDataType.String, filterable=True, facetable=True),
                SimpleField(name="chunk_index", type=SearchFieldDataType.Int32, filterable=True),
                SimpleField(name="content_type", type=SearchFieldDataType.String, filterable=True, facetable=True),
                SimpleField(name="chunk_method", type=SearchFieldDataType.String, filterable=True),
                SimpleField(name="file_size", type=SearchFieldDataType.Int64, filterable=True),
                SimpleField(name="document_url", type=SearchFieldDataType.String),
                SearchField(
                    name="content_vector", 
                    type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
                    searchable=True,
                    vector_search_dimensions=1536,
                    vector_search_profile_name="default-vector-profile"
                )
            ]
            
            # Configure vector search
            vector_search = VectorSearch(
                algorithms=[
                    HnswAlgorithmConfiguration(
                        name="default-hnsw",
                        parameters={
                            "m": 4,
                            "efConstruction": 400,
                            "efSearch": 500,
                            "metric": "cosine"
                        }
                    )
                ],
                profiles=[
                    VectorSearchProfile(
                        name="default-vector-profile",
                        algorithm_configuration_name="default-hnsw"
                    )
                ]
            )
              # Configure semantic search with SEC-specific fields
            semantic_config = SemanticConfiguration(
                name="default-semantic-config",
                prioritized_fields=SemanticPrioritizedFields(
                    title_field=SemanticField(field_name="title"),
                    content_fields=[
                        SemanticField(field_name="content"),
                        SemanticField(field_name="section_type")
                    ],                    keywords_fields=[
                        SemanticField(field_name="ticker"),
                        SemanticField(field_name="company"),
                        SemanticField(field_name="form_type"),
                        SemanticField(field_name="document_type"),
                        SemanticField(field_name="industry"),
                        SemanticField(field_name="entity_type")
                    ]
                )
            )
            
            semantic_search = SemanticSearch(
                configurations=[semantic_config],
                default_configuration_name="default-semantic-config"
            )
              # Create the index
            index = SearchIndex(
                name=settings.search_index,
                fields=fields,
                vector_search=vector_search,
                semantic_search=semantic_search
            )
            result = self.search_index_client.create_index(index)
            logger.info(f"Successfully created search index '{settings.AZURE_SEARCH_INDEX_NAME}'")
            return True
        except Exception as e:
            logger.error(f"Failed to ensure search index exists: {e}")
            return False
        
    async def _create_enhanced_search_index(self):
        """Create enhanced search index with comprehensive schema"""
        from azure.search.documents.indexes.models import (
            SearchIndex, SearchField, SearchFieldDataType, SimpleField, 
            SearchableField, VectorSearch, HnswAlgorithmConfiguration,
            VectorSearchProfile, SemanticConfiguration, SemanticPrioritizedFields,
            SemanticField, SemanticSearch, ScoringProfile, TextWeights
        )
        
        fields = [
            # Core fields
            SimpleField(name="id", type=SearchFieldDataType.String, key=True),
            SimpleField(name="chunk_id", type=SearchFieldDataType.String, filterable=True, sortable=True),
            SearchableField(name="content", type=SearchFieldDataType.String, analyzer_name="en.microsoft"),
            SearchableField(name="title", type=SearchFieldDataType.String),
            SearchableField(name="source", type=SearchFieldDataType.String, filterable=True, facetable=True),
            
            # Document metadata
            SearchableField(name="company", type=SearchFieldDataType.String, filterable=True, facetable=True),
            SimpleField(name="year", type=SearchFieldDataType.String, filterable=True, facetable=True),
            SearchableField(name="document_type", type=SearchFieldDataType.String, filterable=True, facetable=True),
            SimpleField(name="filing_date", type=SearchFieldDataType.String, filterable=True, sortable=True),
            
            SimpleField(name="document_id", type=SearchFieldDataType.String, filterable=True),
            SimpleField(name="section_type", type=SearchFieldDataType.String, filterable=True),
            SimpleField(name="page_number", type=SearchFieldDataType.Int32, filterable=True),
            SimpleField(name="citation_info", type=SearchFieldDataType.String, filterable=True),
            # SEC-specific fields from Edgar tools
            SimpleField(name="ticker", type=SearchFieldDataType.String, filterable=True),
            SimpleField(name="cik", type=SearchFieldDataType.String, filterable=True),
            SimpleField(name="industry", type=SearchFieldDataType.String, filterable=True),
            SimpleField(name="sic", type=SearchFieldDataType.String, filterable=True),
            SimpleField(name="entity_type", type=SearchFieldDataType.String, filterable=True),
            SimpleField(name="form_type", type=SearchFieldDataType.String, filterable=True),
            SimpleField(name="accession_number", type=SearchFieldDataType.String, filterable=True),
            SimpleField(name="period_end_date", type=SearchFieldDataType.String, filterable=True),
            SimpleField(name="chunk_method", type=SearchFieldDataType.String, filterable=True),
            SimpleField(name="document_url", type=SearchFieldDataType.String),


            # Content analysis fields
            SimpleField(name="chunk_index", type=SearchFieldDataType.Int32, filterable=True, sortable=True),
            SimpleField(name="content_length", type=SearchFieldDataType.Int32, filterable=True, sortable=True),
            SimpleField(name="word_count", type=SearchFieldDataType.Int32, filterable=True, sortable=True),
            SimpleField(name="credibility_score", type=SearchFieldDataType.Double, filterable=True, sortable=True),
            SimpleField(name="has_structured_content", type=SearchFieldDataType.Boolean, filterable=True),
            SearchableField(name="structure_info", type=SearchFieldDataType.String, searchable=False),
            
            # Processing metadata
            SimpleField(name="processed_at", type=SearchFieldDataType.String, filterable=True),
            SimpleField(name="processing_method", type=SearchFieldDataType.String, filterable=True),
            SimpleField(name="file_size", type=SearchFieldDataType.Int64, filterable=True),
            
            # Vector embeddings
            SearchField(
                name="content_vector",
                type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
                searchable=True,
                retrievable=True,
                vector_search_dimensions=1536,  # text-embedding-3-small dimensions
                vector_search_profile_name="vector-profile"
            ),
            SimpleField(name="embedding_model", type=SearchFieldDataType.String, filterable=True),
            SimpleField(name="embedding_dimensions", type=SearchFieldDataType.Int32, filterable=True),
        ]
        
        # Vector search configuration
        vector_search = VectorSearch(
            algorithms=[
                HnswAlgorithmConfiguration(
                    name="hnsw-config",
                    parameters={
                        "m": 4,
                        "efConstruction": 400,
                        "efSearch": 500,
                        "metric": "cosine"
                    }
                )
            ],
            profiles=[
                VectorSearchProfile(
                    name="vector-profile",
                    algorithm_configuration_name="hnsw-config"
                )
            ]
        )
        
        # Semantic search configuration
        semantic_config = SemanticConfiguration(
            name="default",
            prioritized_fields=SemanticPrioritizedFields(
                title_field=SemanticField(field_name="title"),
                content_fields=[
                    SemanticField(field_name="content"),
                    SemanticField(field_name="structure_info")
                ],
                keywords_fields=[
                    SemanticField(field_name="company"),
                    SemanticField(field_name="document_type"),
                    SemanticField(field_name="source")
                ]
            )
        )
        
        semantic_search = SemanticSearch(configurations=[semantic_config])
        
        # Scoring profiles for enhanced relevance
        scoring_profiles = [
            ScoringProfile(
                name="financial-document-scoring",
                text_weights=TextWeights(
                    weights={
                        "content": 1.0,
                        "title": 0.8,
                        "company": 0.5,
                        "source": 0.3
                    }
                )
            ),
            ScoringProfile(
                name="credibility-boost", 
                text_weights=TextWeights(
                    weights={
                        "content": 1.0,
                        "company": 0.8,
                        "document_type": 0.6
                    }
                )
            )
        ]
        
        # Create the index
        index = SearchIndex(
            name=settings.search_index,
            fields=fields,
            vector_search=vector_search,
            semantic_search=semantic_search,
            scoring_profiles=scoring_profiles,
            default_scoring_profile="financial-document-scoring"
        )
        
        return index
    
    async def recreate_search_index(self, force: bool = False) -> bool:
        """
        Force recreate the search index with the latest schema.
        This will delete the existing index and create a new one.
        Use with caution as this will delete all existing data.
        """
        try:
            if not force:
                logger.warning("recreate_search_index() will DELETE all existing data. Call with force=True to proceed.")
                return False
            
            if self._use_mock:
                logger.info("Using mock services - simulating index recreation")
                return True
                
            logger.info(f"Force recreating search index '{settings.search_index}'")
            
            # Delete existing index if it exists
            try:
                self.search_index_client.delete_index(settings.search_index)
                logger.info(f"Deleted existing index '{settings.search_index}'")
            except Exception as e:
                logger.info(f"No existing index to delete: {e}")
            
            # Create fresh index
            return await self.ensure_search_index_exists()
            
        except Exception as e:
            logger.error(f"Failed to recreate search index: {e}")
            return False
    
    async def recreate_search_index_with_facetable_fields(self) -> bool:
        """
        Recreate the search index with facetable fields enabled.
        WARNING: This will delete all existing data in the index.
        """
        try:
            logger.warning("Recreating search index - this will delete all existing data!")
            
            # Delete existing index if it exists
            try:
                self.search_index_client.delete_index(settings.search_index)
                logger.info(f"Deleted existing index '{settings.search_index}'")
            except Exception as e:
                logger.info(f"Index may not exist: {e}")
            
            # Create new index with facetable fields
            result = await self.ensure_search_index_exists()
            
            if result:
                logger.info("Successfully recreated search index with facetable fields")
                logger.warning("You will need to re-ingest all documents to populate the new index")
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to recreate search index: {e}")
            return False
    
    async def check_document_exists(self, accession_number: str) -> bool:
        """Check if a document with the given accession number already exists in the search index"""
        try:
            logger.info(f"Checking if document exists in index: {accession_number}")
            
            indexExists = await self.ensure_search_index_exists()
            if not indexExists:
                logger.error("Search index does not exist, creating it now")
                
            # Search for documents with the specific accession number using async client
            search_results = await self.async_search_client.search(
                search_text="*",
                filter=f"accession_number eq '{accession_number}'",
                select=["id", "accession_number"],
                top=1
            )
            
            # Convert async results to list to check if any documents exist
            documents = []
            async for result in search_results:
                documents.append(result)
                
            exists = len(documents) > 0
            
            if exists:
                logger.info(f"Document with accession number {accession_number} already exists in index")
            else:
                logger.info(f"Document with accession number {accession_number} not found in index")
                
            return exists
            
        except Exception as e:
            logger.error(f"Error checking if document exists: {e}")
            # In case of error, assume document doesn't exist to allow processing
            return False

    async def get_embedding(self, text: str, model: str = None) -> List[float]:
        """Get embedding for text using Azure OpenAI async client"""
        try:
            if self._use_mock:
                import random
                return [random.random() for _ in range(1536)]
            
            if not self.async_openai_client:
                raise ValueError("Azure OpenAI client not initialized")
            
            # Use deployment name from settings
            deployment_name = model or getattr(settings, 'OPENAI_EMBED_DEPLOYMENT', 'embeddingsmall')
            
            logger.debug(f"Getting embedding for {len(text)} chars using {deployment_name}")
            
            response = await self.async_openai_client.embeddings.create(
                input=text,
                model=deployment_name
            )
            
            return response.data[0].embedding
            
        except Exception as e:
            logger.error(f"Failed to get embedding: {e}")
            raise
    
    async def hybrid_search(self, query: str, top_k: int = 10, filters: str = None, min_score: float = 0.0) -> List[Dict]:
        """Perform hybrid search (vector + keyword) on the knowledge base"""
        try:
            if self._use_mock:
                return self.search_client.search(query)
            
            logger.debug(f"Hybrid search for query: '{query[:50]}...' (top_k={top_k})")
            
            query_vector = await self.get_embedding(query)
            vector_query = VectorizedQuery(
                vector=query_vector,
                k_nearest_neighbors=top_k,
                fields="content_vector"
            )
            
            search_results = await self.async_search_client.search(
                search_text=query,
                vector_queries=[vector_query],
                select=["id", "content", "title", "source", "company", "filing_date", 
                       "document_type", "chunk_index", "credibility_score", "processed_at",
                       "content_length", "word_count", "has_structured_content"],
                filter=filters,
                top=top_k,
                query_type="semantic",
                semantic_configuration_name="default"
            )
            
            # Filter results by minimum score if specified
            filtered_results = []
            async for result in search_results:
                result_dict = dict(result)
                score = getattr(result, '@search.score', 0.0)
                if score >= min_score:
                    result_dict['search_score'] = score
                    filtered_results.append(result_dict)
            
            logger.debug(f"Hybrid search completed, found: {len(filtered_results)} results")
            return filtered_results
            
        except Exception as e:
            logger.error(f"Hybrid search failed: {e}")
            raise
    
    async def add_documents_to_index(self, documents: List[Dict]) -> bool:
        """Add or update documents in the search index"""
        try:
            if self._use_mock:
                return True
            
            logger.info(f"Adding {len(documents)} documents to search index")
            
            validated_documents = []
            for doc in documents:
                if self._validate_document_schema(doc):
                    validated_documents.append(doc)
                else:
                    logger.warning(f"Skipping invalid document: {doc.get('id', 'unknown')}")
                    
            if not validated_documents:
                logger.error("No valid documents to upload after validation")
                return False
            
            # Use sync client for upload
            result = self.search_client_upload.upload_documents(validated_documents)
            logger.info(f"Successfully uploaded {len(validated_documents)} documents")
            return True
                
        except Exception as e:
            logger.error(f"Failed to add documents to index: {e}")
            return False
    
    def _validate_document_schema(self, document: Dict) -> bool:
        """Validate document schema before uploading to search index"""
        required_fields = ['id', 'content']
        for field in required_fields:
            if field not in document or not document[field]:
                logger.warning(f"Document missing required field: {field}")
                return False
        
        if len(document['content']) > 1000000:  # 1MB limit
            logger.warning(f"Document content too large: {len(document['content'])} characters")
            return False
            
        return True
    
    async def analyze_document(self, document_content: bytes, content_type: str, filename: str = None) -> Dict:
        """Analyze document using Azure Document Intelligence"""
        try:
            if self._use_mock:
                logger.info(f"Using mock Document Intelligence for {filename or 'document'}")
                # Simulate processing delay for realistic experience
                await asyncio.sleep(0.5)
                
                # Generate more realistic mock content
                mock_content = self._generate_realistic_mock_content(filename, len(document_content))
                
                return {
                    "content": mock_content,
                    "tables": [
                        {
                            "table_id": 0,
                            "cells": [
                                {"content": "Total Revenue", "row_index": 0, "column_index": 0, "confidence": 0.95},
                                {"content": "$15.2 billion", "row_index": 0, "column_index": 1, "confidence": 0.92}
                            ]
                        }
                    ],
                    "key_value_pairs": {
                        "Company Name": {"value": self._extract_company_from_filename(filename), "confidence": 0.9},
                        "Filing Date": {"value": "2023-12-31", "confidence": 0.85},
                        "Document Type": {"value": "10-K Annual Report", "confidence": 0.88}
                    },
                    "pages": max(1, len(document_content) // 50000),  # Estimate pages
                    "metadata": {"model_used": "mock-prebuilt-layout", "confidence": 0.9}
                }
            
            if not self.form_recognizer_client:
                raise ValueError("Document Intelligence client not initialized")
            
            model_id = self._select_document_model(content_type, filename)
            logger.info(f"Analyzing document with model {model_id}, size: {len(document_content)} bytes")
            
            poller = self.form_recognizer_client.begin_analyze_document(
                model_id=model_id,
                body=document_content,
                content_type=content_type
            )
            result = poller.result()
            
            extracted_content = {
                "content": result.content,
                "tables": [],
                "key_value_pairs": {},
                "pages": len(result.pages) if result.pages else 0,
                "metadata": {
                    "model_used": model_id,
                    "confidence_scores": {}
                }
            }
            
            # Extract tables
            if result.tables:
                for i, table in enumerate(result.tables):
                    table_data = {
                        "table_id": i,
                        "cells": []
                    }
                    
                    for cell in table.cells:
                        table_data["cells"].append({
                            "content": cell.content,
                            "row_index": cell.row_index,
                            "column_index": cell.column_index,
                            "confidence": getattr(cell, 'confidence', 0.0)
                        })
                    
                    extracted_content["tables"].append(table_data)
            
            # Extract key-value pairs
            if result.key_value_pairs:
                for kv_pair in result.key_value_pairs:
                    if kv_pair.key and kv_pair.value:
                        key_content = kv_pair.key.content
                        value_content = kv_pair.value.content
                        
                        extracted_content["key_value_pairs"][key_content] = {
                            "value": value_content,
                            "confidence": getattr(kv_pair, 'confidence', 0.0)
                        }
            
            logger.info(f"Document analysis completed: {extracted_content['pages']} pages, {len(extracted_content['tables'])} tables")
            return extracted_content
                
        except Exception as e:
            logger.error(f"Document analysis failed: {e}")
            raise
    
    def _select_document_model(self, content_type: str, filename: str = None) -> str:
        """Select appropriate Document Intelligence model based on content type and filename"""
        if filename:
            filename_lower = filename.lower()
            if any(term in filename_lower for term in ['10-k', '10k', '10-q', '10q', 'annual', 'quarterly']):
                return "prebuilt-layout"  # Best for structured financial documents
        
        if content_type == "application/pdf":
            return "prebuilt-layout"
        elif content_type in ["application/vnd.openxmlformats-officedocument.wordprocessingml.document", "application/msword"]:
            return "prebuilt-document"
        else:
            return "prebuilt-document"
    
    async def get_index_stats(self) -> Dict[str, Any]:
        """Get statistics about the search index"""
        try:
            if self._use_mock:
                return {
                    "total_documents": 2847,
                    "company_breakdown": {
                        "Apple": 486,
                        "Google": 523,
                        "Microsoft": 467,
                        "Meta": 398,
                        "JPMC": 512,
                        "Amazon": 461
                    }
                }
            
            # Get total document count using sync client for simplicity
            search_results = self.search_client.search(
                "*", 
                include_total_count=True, 
                top=0
            )
            
            try:
                total_documents = search_results.get_count()
            except:
                total_documents = 0
            
            # Get company breakdown using facets - use sync client for simplicity
            try:
                company_results = self.search_client.search(
                    "*",
                    facets=["company"],
                    top=0
                )
                
                company_breakdown = {}
                facets = company_results.get_facets()
                if facets and 'company' in facets:
                    for facet in facets['company']:
                        company_breakdown[facet['value']] = facet['count']
            except Exception as facet_error:
                logger.warning(f"Failed to get company facets: {facet_error}")
                logger.info("This might be due to the 'company' field not being facetable. Consider recreating the index.")
                company_breakdown = {
                    "note": "Company facets unavailable - field may not be facetable",
                    "total_count": total_documents
                }
            
            return {
                "total_documents": total_documents,
                "company_breakdown": company_breakdown
            }
            
        except Exception as e:
            logger.error(f"Failed to get index stats: {e}")
            return {"error": str(e), "total_documents": 0, "company_breakdown": {}}
    
    def _generate_realistic_mock_content(self, filename: str, file_size: int) -> str:
        """Generate realistic mock content based on filename and file size"""
        company = self._extract_company_from_filename(filename)
        
        mock_content = f"""
UNITED STATES
SECURITIES AND EXCHANGE COMMISSION
Washington, D.C. 20549

FORM 10-K

ANNUAL REPORT PURSUANT TO SECTION 13 OR 15(d) OF THE SECURITIES EXCHANGE ACT OF 1934

For the fiscal year ended December 31, 2023

Commission File Number: 001-12345

{company.upper()} CORPORATION
(Exact name of registrant as specified in its charter)

Delaware                                              12-3456789
(State of incorporation)                           (I.R.S. Employer Identification No.)

BUSINESS OVERVIEW

{company} is a technology company that develops and markets consumer electronics, computer software, and online services. The company was founded in the early 1990s and has grown to become one of the world's largest technology companies.

FINANCIAL HIGHLIGHTS

For the fiscal year 2023:
- Total revenue: $15.2 billion
- Net income: $3.8 billion 
- Total assets: $45.6 billion
- Cash and cash equivalents: $12.3 billion

RISK FACTORS

The following risk factors may materially affect our business:
1. Competition in the technology sector
2. Regulatory changes and compliance requirements
3. Cybersecurity threats and data protection
4. Supply chain disruptions
5. Economic uncertainties and market volatility

MANAGEMENT'S DISCUSSION AND ANALYSIS

Our financial performance in 2023 reflected strong growth across all business segments. Revenue increased by 12% compared to the previous year, driven by robust demand for our products and services.

CONSOLIDATED STATEMENTS OF OPERATIONS
(In millions, except per share data)

                               2023      2022      2021
Revenue                       $15,200   $13,580   $12,100
Cost of revenue                8,900     8,200     7,500
Gross profit                   6,300     5,380     4,600
Operating expenses             3,200     2,950     2,800
Operating income               3,100     2,430     1,800
Net income                     3,800     2,100     1,600

This mock document represents a typical 10-K annual report structure with financial data and business information.
        """.strip()
        
        # Adjust content length based on file size for realism
        if file_size > 500000:  # Large file
            mock_content += "\n\n" + mock_content  # Repeat content
        
        return mock_content
    
    def _extract_company_from_filename(self, filename: str) -> str:
        """Extract company name from filename"""
        if not filename:
            return "Sample Corporation"
        
        filename_lower = filename.lower()
        
        # Common company identifiers in filenames
        if 'fb' in filename_lower or 'meta' in filename_lower:
            return "Meta Platforms Inc"
        elif 'aapl' in filename_lower or 'apple' in filename_lower:
            return "Apple Inc"
        elif 'msft' in filename_lower or 'microsoft' in filename_lower:
            return "Microsoft Corporation"
        elif 'googl' in filename_lower or 'google' in filename_lower:
            return "Alphabet Inc"
        elif 'amzn' in filename_lower or 'amazon' in filename_lower:
            return "Amazon.com Inc"
        elif 'tsla' in filename_lower or 'tesla' in filename_lower:
            return "Tesla Inc"
        else:
            return "Sample Financial Corporation"

    async def save_session_history(self, session_id: str, message: Dict) -> tuple[bool, str]:
        """Save chat session history to CosmosDB"""
        original_session_id = session_id  # Store original value at start
        try:
            # Generate a new session ID if none provided or empty
            if not session_id or session_id.strip() == "":
                session_id = str(uuid.uuid4())
                logger.info(f"Generated new session ID: {session_id}")
            
            logger.info(f"Attempting to save session {session_id} - Mock mode: {self._use_mock}, CosmosDB client: {self.cosmos_client is not None}")
            
            if self._use_mock:
                logger.info(f"Mock mode enabled - skipping session history save for {session_id}")
                return True, session_id
                
            if not self.cosmos_client:
                logger.warning(f"CosmosDB client not available - skipping session history save for {session_id}")
                logger.warning(f"CosmosDB endpoint configured: {getattr(settings, 'azure_cosmos_endpoint', 'NOT_SET')}")
                return False, session_id
            
            database = self.cosmos_client.get_database_client(settings.azure_cosmos_database_name)
            container = database.get_container_client(settings.azure_cosmos_container_name)
            
            try:
                session_doc = container.read_item(item=session_id, partition_key=session_id)
                logger.info(f"Found existing session document for {session_id}")
            except:
                logger.info(f"Creating new session document for {session_id}")
                session_doc = {
                    "id": session_id,
                    "messages": [],
                    "created_at": message.get("timestamp"),
                    "updated_at": message.get("timestamp"),
                    "user_id": message.get("user_id", "unknown"),
                    "mode": message.get("mode", "unknown")
                }
            
            # Ensure required fields exist (for backward compatibility with existing documents)
            if "messages" not in session_doc:
                session_doc["messages"] = []
            if "user_id" not in session_doc:
                session_doc["user_id"] = message.get("user_id", "unknown")
            if "mode" not in session_doc:
                session_doc["mode"] = message.get("mode", "unknown")
                
            # Clean and validate the message before adding it
            import json
            
            # Debug: Log the original message structure
            logger.info(f"Original message keys: {list(message.keys()) if message else 'None'}")
            logger.info(f"Original message role: {message.get('role', 'MISSING') if message else 'None'}")
            
            cleaned_message = {}
            for key, value in message.items():
                try:
                    # Ensure the value can be JSON serialized
                    json.dumps(value, default=str)
                    cleaned_message[key] = value
                except (TypeError, ValueError) as e:
                    logger.warning(f"Skipping non-serializable field '{key}': {e}")
                    cleaned_message[key] = str(value)  # Convert to string as fallback
            
            # Debug: Log the cleaned message structure
            logger.info(f"Cleaned message keys: {list(cleaned_message.keys())}")
            logger.info(f"Cleaned message role: {cleaned_message.get('role', 'MISSING')}")
                    
            session_doc["messages"].append(cleaned_message)
            session_doc["updated_at"] = message.get("timestamp")
            
            # Validate and clean the document before saving
            try:
                # Check for valid session_id and document id
                if not session_id or session_id.strip() == "":
                    logger.error(f"Invalid session_id: '{session_id}' - cannot save to CosmosDB")
                    return False
                
                if "id" not in session_doc or not session_doc["id"] or session_doc["id"].strip() == "":
                    logger.error(f"Invalid document id: '{session_doc.get('id', 'MISSING')}' - setting to session_id")
                    session_doc["id"] = session_id
                
                # Ensure document can be JSON serialized
                json_str = json.dumps(session_doc, default=str)
                
                # Check document size (CosmosDB has 2MB limit)
                doc_size = len(json_str.encode('utf-8'))
                if doc_size > 1.8 * 1024 * 1024:  # 1.8MB safety margin
                    logger.warning(f"Session document size ({doc_size} bytes) approaching CosmosDB limit")
                    # Trim old messages if document is too large
                    while len(session_doc["messages"]) > 10 and doc_size > 1.8 * 1024 * 1024:
                        session_doc["messages"].pop(0)  # Remove oldest message
                        doc_size = len(json.dumps(session_doc, default=str).encode('utf-8'))
                        
                logger.debug(f"Saving session document ID: '{session_doc['id']}' with {len(session_doc['messages'])} messages, size: {doc_size} bytes")
                
                # Log document structure for debugging
                if logger.isEnabledFor(logging.DEBUG):
                    logger.debug(f"Document structure: {list(session_doc.keys())}")
                    logger.debug(f"Latest message keys: {list(cleaned_message.keys()) if cleaned_message else 'None'}")
                
            except Exception as validation_error:
                logger.error(f"Session document validation failed: {validation_error}")
                logger.error(f"Session ID: '{session_id}'")
                logger.error(f"Document keys: {list(session_doc.keys())}")
                logger.error(f"Document ID field: '{session_doc.get('id', 'MISSING')}'")
                logger.error(f"Message keys: {list(message.keys()) if message else 'None'}")
                return False, session_id
            
            container.upsert_item(session_doc)
            logger.info(f"Successfully saved session {session_id} to CosmosDB with {len(session_doc['messages'])} messages")
            return True, session_id
            
        except Exception as e:
            # Use the current session_id value, or original if there was an error
            error_session_id = session_id if 'session_id' in locals() else original_session_id
            
            logger.error(f"Failed to save session history for {error_session_id}: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            
            # Additional debugging for CosmosDB errors
            if "BadRequest" in str(e) and "invalid" in str(e).lower():
                logger.error(f"CosmosDB BadRequest Details:")
                logger.error(f"  - Session ID: '{error_session_id}'")
                logger.error(f"  - Document ID: '{session_doc.get('id', 'MISSING') if 'session_doc' in locals() else 'NOT_CREATED'}'")
                logger.error(f"  - Document size: {len(json.dumps(session_doc, default=str)) if 'session_doc' in locals() else 'UNKNOWN'} chars")
                logger.error(f"  - Message count: {len(session_doc.get('messages', [])) if 'session_doc' in locals() else 'UNKNOWN'}")
                logger.error(f"  - Document keys: {list(session_doc.keys()) if 'session_doc' in locals() else 'NOT_CREATED'}")
                
                # Try to identify problematic fields
                if 'session_doc' in locals():
                    for key, value in session_doc.items():
                        try:
                            json.dumps({key: value}, default=str)
                        except Exception as field_error:
                            logger.error(f"  - Problematic field '{key}': {field_error}")
            
            return False, error_session_id

    async def get_session_history(self, session_id: str) -> List[Dict]:
        """Retrieve chat session history from CosmosDB"""
        session_data = await self.get_session_data(session_id)
        return session_data.get("messages", [])

    async def get_session_data(self, session_id: str) -> Dict:
        """Retrieve full session data (messages + metadata) from CosmosDB"""
        try:
            if self._use_mock or not self.cosmos_client:
                logger.info(f"Mock mode or CosmosDB not available - returning empty data for {session_id}")
                return {"messages": [], "mode": "fast-rag", "created_at": None, "updated_at": None}
            
            database = self.cosmos_client.get_database_client(settings.azure_cosmos_database_name)
            container = database.get_container_client(settings.azure_cosmos_container_name)
            
            try:
                logger.info(f"Attempting to retrieve session {session_id} from CosmosDB")
                logger.info(f"Database: {settings.azure_cosmos_database_name}, Container: {settings.azure_cosmos_container_name}")
                logger.info(f"Using partition key: {session_id}")
                
                # First, let's try to query for the document to see if it exists
                query_results = container.query_items(
                    query="SELECT * FROM c WHERE c.id = @session_id",
                    parameters=[{"name": "@session_id", "value": session_id}],
                    enable_cross_partition_query=True
                )
                
                documents = []
                for doc in query_results:
                    documents.append(doc)
                
                if documents:
                    logger.info(f"Found session document via query: {len(documents)} documents")
                    session_doc = documents[0]
                    logger.info(f"Document structure: id={session_doc.get('id')}, user_id={session_doc.get('user_id')}, messages_count={len(session_doc.get('messages', []))}, mode={session_doc.get('mode', 'unknown')}")
                    return session_doc
                else:
                    logger.warning(f"No documents found for session_id {session_id} via query")
                    return {"messages": [], "mode": "fast-rag", "created_at": None, "updated_at": None}
                
            except Exception as e:
                # Session doesn't exist yet, return empty data
                if "NotFound" in str(e) or "does not exist" in str(e) or "404" in str(e):
                    logger.info(f"Session {session_id} not found, returning empty data")
                    # Let's also check if any sessions exist at all
                    try:
                        query_results = container.query_items(
                            query="SELECT c.id FROM c",
                            max_item_count=5,
                            enable_cross_partition_query=True
                        )
                        existing_sessions = []
                        for item in query_results:
                            existing_sessions.append(item.get('id'))
                            if len(existing_sessions) >= 5:
                                break
                        logger.info(f"Sample existing session IDs in database: {existing_sessions}")
                    except Exception as query_e:
                        logger.warning(f"Could not query existing sessions: {query_e}")
                    return {"messages": [], "mode": "fast-rag", "created_at": None, "updated_at": None}
                else:
                    # Some other error occurred
                    logger.error(f"Failed to retrieve session data: {e}")
                    return {"messages": [], "mode": "fast-rag", "created_at": None, "updated_at": None}
        except Exception as e:
            logger.error(f"Failed to retrieve session data: {e}")
            return {"messages": [], "mode": "fast-rag", "created_at": None, "updated_at": None}

    async def list_user_sessions(self, user_id: str, limit: int = 50, offset: int = 0, mode_filter: str = None) -> List[Dict]:
        """List sessions for a specific user from CosmosDB"""
        try:
            if self._use_mock or not self.cosmos_client:
                logger.info(f"Mock mode or CosmosDB not available - returning empty sessions list for user {user_id}")
                return []
            
            database = self.cosmos_client.get_database_client(settings.azure_cosmos_database_name)
            container = database.get_container_client(settings.azure_cosmos_container_name)
            
            # Build query to find sessions for this user
            query = "SELECT * FROM c WHERE c.user_id = @user_id ORDER BY c.updated_at DESC"
            parameters = [{"name": "@user_id", "value": user_id}]
            
            if mode_filter:
                query = "SELECT * FROM c WHERE c.user_id = @user_id AND c.mode = @mode ORDER BY c.updated_at DESC"
                parameters.append({"name": "@mode", "value": mode_filter})
            
            # Execute query with pagination
            query_results = container.query_items(
                query=query,
                parameters=parameters,
                max_item_count=limit,
                enable_cross_partition_query=True
            )
            
            sessions = []
            count = 0
            skip_count = 0
            
            for item in query_results:
                if skip_count < offset:
                    skip_count += 1
                    continue
                    
                if count >= limit:
                    break
                
                # Extract session metadata
                messages = item.get("messages", [])
                session_summary = {
                    "session_id": item.get("id", ""),
                    "created_at": item.get("created_at", ""),
                    "updated_at": item.get("updated_at", ""),
                    "message_count": len(messages),
                    "mode": self._extract_mode_from_messages(messages),
                    "last_user_message": self._get_last_user_message(messages),
                    "total_tokens": self._calculate_total_tokens(messages),
                    "session_title": self._generate_session_title(messages)
                }
                sessions.append(session_summary)
                count += 1
            
            logger.info(f"Retrieved {len(sessions)} sessions for user {user_id}")
            return sessions
            
        except Exception as e:
            logger.error(f"Failed to list user sessions: {e}")
            return []

    async def get_conversation_context(self, session_id: str, limit: int = 10) -> List[Dict]:
        """Get recent conversation context for maintaining continuity"""
        try:
            messages = await self.get_session_history(session_id)
            if not messages:
                return []
            
            # Return last 'limit' messages for context (alternating user/assistant pairs)
            context_messages = messages[-limit:] if len(messages) > limit else messages
            
            # Format for conversation context
            formatted_context = []
            for msg in context_messages:
                if msg.get("role") in ["user", "assistant"]:
                    formatted_context.append({
                        "role": msg.get("role"),
                        "content": msg.get("content", ""),
                        "timestamp": msg.get("timestamp", "")
                    })
            
            return formatted_context
            
        except Exception as e:
            logger.error(f"Failed to get conversation context: {e}")
            return []

    def _extract_mode_from_messages(self, messages: List[Dict]) -> str:
        """Extract the RAG mode from message history"""
        for msg in reversed(messages):
            mode = msg.get("mode")
            if mode:
                return mode
        return "unknown"

    def _get_last_user_message(self, messages: List[Dict]) -> str:
        """Get the last user message for session preview"""
        for msg in reversed(messages):
            if msg.get("role") == "user":
                content = msg.get("content", "")
                return content[:100] + "..." if len(content) > 100 else content
        return "No messages"

    def _calculate_total_tokens(self, messages: List[Dict]) -> int:
        """Calculate total tokens used in the session"""
        total = 0
        for msg in messages:
            if msg.get("role") == "assistant":
                token_usage = msg.get("token_usage", {})
                total += token_usage.get("total_tokens", 0)
        return total

    def _generate_session_title(self, messages: List[Dict]) -> str:
        """Generate a title for the session based on the first user message"""
        for msg in messages:
            if msg.get("role") == "user":
                content = msg.get("content", "")
                # Take first sentence or first 50 characters
                if "." in content[:100]:
                    title = content[:content.index(".", 0, 100) + 1]
                else:
                    title = content[:50] + "..." if len(content) > 50 else content
                return title.strip()
        return "New Chat"

    # ...existing code...
    
    @property
    def embedding_client(self):
        """Property to access the embedding client (for status checks)"""
        return self.async_openai_client
    
    def _check_if_index_needs_facetable_update(self, existing_index) -> bool:
        """Check if the existing index needs to be updated for facetable fields"""
        try:
            # Check if the company field exists and is facetable
            for field in existing_index.fields:
                if field.name == "company":
                    # If company field exists but is not facetable, we need to update
                    if not getattr(field, 'facetable', False):
                        logger.info("Company field exists but is not facetable. Index needs updating.")
                        return True
                    break
            return False
        except Exception as e:
            logger.warning(f"Could not check index schema: {e}")
            return False
    
# Global service manager instance
azure_service_manager = AzureServiceManager()

async def get_azure_service_manager() -> AzureServiceManager:
    """Get the global Azure service manager instance"""
    if not azure_service_manager.search_client:
        await azure_service_manager.initialize()
    return azure_service_manager

async def cleanup_azure_services():
    """Cleanup Azure services"""
    await azure_service_manager.cleanup()