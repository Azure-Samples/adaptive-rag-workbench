"""
Azure AI Search HTTP API Server for Adaptive RAG Workbench
Provides HTTP API endpoints that wrap Azure AI Search functionality.
This serves as an HTTP API for Azure Search operations instead of MCP protocol.
"""

import os
import sys
import logging
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv
from azure.core.credentials import AzureKeyCredential
from azure.identity import DefaultAzureCredential
from azure.search.documents import SearchClient
from azure.search.documents.models import VectorizedQuery, QueryType
from openai import AsyncAzureOpenAI
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Add startup message
print("Starting Azure AI Search HTTP API Server for Adaptive RAG...", file=sys.stderr)

# Load environment variables
load_dotenv()
print("Environment variables loaded", file=sys.stderr)

# Get port configuration
SERVER_PORT = int(os.getenv("MCP_SERVER_PORT", "8006"))
print(f"HTTP API server will run on port: {SERVER_PORT}", file=sys.stderr)

# Create FastAPI app
app = FastAPI(
    title="Azure AI Search API for Adaptive RAG",
    description="HTTP API for Azure AI Search operations",
    version="1.0.0"
)
print("FastAPI app instance created", file=sys.stderr)

# Request/Response models
class SearchRequest(BaseModel):
    query: str
    top: int = 5
    filters: str = ""

class SearchResponse(BaseModel):
    results: List[Dict[str, Any]]
    total_found: int
    search_type: str

class AzureSearchClient:
    """
    Enhanced Azure AI Search client with security best practices and error handling.
    Uses managed identity when available, falls back to API key authentication.
    """
    
    def __init__(self):
        """Initialize Azure Search client with secure authentication."""
        print("Initializing Azure Search client...", file=sys.stderr)
        
        # Load environment variables
        self.endpoint = os.getenv("AZURE_SEARCH_SERVICE_ENDPOINT")
        self.index_name = os.getenv("AZURE_SEARCH_INDEX_NAME", "adaptive-rag-index")
        api_key = os.getenv("AZURE_SEARCH_API_KEY")
        
        # OpenAI configuration for embeddings
        self.openai_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
        self.openai_key = os.getenv("AZURE_OPENAI_KEY")
        self.openai_api_version = os.getenv("AZURE_OPENAI_API_VERSION", "2024-08-01-preview")
        self.embedding_deployment = os.getenv("OPENAI_EMBED_DEPLOYMENT", "embeddingsmall")
        
        # Validate required environment variables
        if not self.endpoint:
            error_msg = "Missing required environment variable: AZURE_SEARCH_SERVICE_ENDPOINT"
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        if not self.index_name:
            error_msg = "Missing required environment variable: AZURE_SEARCH_INDEX_NAME"
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        # Initialize credentials - prefer managed identity
        try:
            if api_key:
                logger.info("Using API key authentication")
                self.credential = AzureKeyCredential(api_key)
            else:
                logger.info("Using managed identity authentication")
                self.credential = DefaultAzureCredential()
        except Exception as e:
            logger.error(f"Failed to initialize credentials: {str(e)}")
            raise
        
        # Initialize the search client
        try:
            logger.info(f"Connecting to Azure AI Search at {self.endpoint}")
            self.search_client = SearchClient(
                endpoint=self.endpoint,
                index_name=self.index_name,
                credential=self.credential
            )
            logger.info(f"Azure Search client initialized for index: {self.index_name}")
        except Exception as e:
            logger.error(f"Failed to initialize search client: {str(e)}")
            raise
        
        # Initialize OpenAI client for embeddings
        try:
            if self.openai_endpoint and self.openai_key:
                self.openai_client = AsyncAzureOpenAI(
                    azure_endpoint=self.openai_endpoint,
                    api_key=self.openai_key,
                    api_version=self.openai_api_version
                )
                logger.info("Azure OpenAI client initialized for embeddings")
            else:
                logger.warning("Azure OpenAI endpoint/key not configured - vector search will not work")
                self.openai_client = None
        except Exception as e:
            logger.error(f"Failed to initialize OpenAI client: {str(e)}")
            self.openai_client = None
    
    async def get_embedding(self, text: str) -> List[float]:
        """Get embedding for text using Azure OpenAI"""
        try:
            if not self.openai_client:
                raise ValueError("OpenAI client not initialized")
            
            logger.debug(f"Getting embedding for {len(text)} chars using {self.embedding_deployment}")
            
            response = await self.openai_client.embeddings.create(
                input=text,
                model=self.embedding_deployment
            )
            
            return response.data[0].embedding
            
        except Exception as e:
            logger.error(f"Failed to get embedding: {e}")
            raise
    
    def keyword_search(self, query: str, top: int = 5, filters: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Perform keyword search on the index with enhanced filtering and ranking.
        """
        logger.info(f"Performing keyword search for: {query}")
        
        try:
            search_params = {
                "search_text": query,
                "top": top,
                "select": ["title", "content", "company", "document_type", 
                          "filing_date", "form_type", "ticker", "chunk_id", "source"],
                "query_type": QueryType.SIMPLE,
                "search_mode": "all"
            }
            
            if filters:
                search_params["filter"] = filters
            
            results = self.search_client.search(**search_params)
            return self._format_results(results, "keyword")
            
        except Exception as e:
            logger.error(f"Error in keyword search: {str(e)}")
            raise
    
    async def vector_search(self, query: str, top: int = 5, vector_field: str = "content_vector", 
                     filters: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Perform vector similarity search on the index.
        """
        logger.info(f"Performing vector search for: {query}")
        
        try:
            # Get embedding for the query
            query_vector = await self.get_embedding(query)
            
            # Create vector query
            vector_query = VectorizedQuery(
                vector=query_vector,
                k_nearest_neighbors=top,
                fields=vector_field
            )
            
            search_params = {
                "vector_queries": [vector_query],
                "top": top,
                "select": ["title", "content", "company", "document_type", 
                          "filing_date", "form_type", "ticker", "chunk_id", "source"]
            }
            
            if filters:
                search_params["filter"] = filters
            
            results = self.search_client.search(**search_params)
            return self._format_results(results, "vector")
            
        except Exception as e:
            logger.error(f"Error in vector search: {str(e)}")
            raise

    async def hybrid_search(self, query: str, top: int = 5, vector_field: str = "content_vector",
                     filters: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Perform hybrid search (keyword + vector) on the index.
        """
        logger.info(f"Performing hybrid search for: {query}")
        
        try:
            # Get embedding for the query
            query_vector = await self.get_embedding(query)
            
            # Create vector query
            vector_query = VectorizedQuery(
                vector=query_vector,
                k_nearest_neighbors=top,
                fields=vector_field
            )
            
            search_params = {
                "search_text": query,
                "vector_queries": [vector_query],
                "top": top,
                "select": ["title", "content", "company", "document_type", 
                          "filing_date", "form_type", "ticker", "chunk_id", "source"],
                "query_type": QueryType.SEMANTIC
            }
            
            if filters:
                search_params["filter"] = filters
            
            results = self.search_client.search(**search_params)
            return self._format_results(results, "hybrid")
            
        except Exception as e:
            logger.error(f"Error in hybrid search: {str(e)}")
            raise

    def _format_results(self, results: Any, search_type: str) -> List[Dict[str, Any]]:
        """
        Format search results for consistent output structure.
        """
        formatted_results = []
        
        try:
            for result in results:
                # Extract content from the 'content' field
                content = result.get("content", "")
                
                item = {
                    "title": result.get("title", "Unknown Document"),
                    "content": content[:2000] if content else "",  # Limit content length
                    "company": result.get("company", ""),
                    "document_type": result.get("document_type", ""),
                    "filing_date": result.get("filing_date", ""),
                    "form_type": result.get("form_type", ""),
                    "ticker": result.get("ticker", ""),
                    "chunk_id": result.get("chunk_id", ""),
                    "source": result.get("source", ""),
                    "search_score": result.get("@search.score", 0),
                    "reranker_score": result.get("@search.reranker_score"),
                    "search_type": search_type
                }
                formatted_results.append(item)
            
            logger.info(f"Formatted {len(formatted_results)} search results")
            return formatted_results
            
        except Exception as e:
            logger.error(f"Error formatting results: {str(e)}")
            return []

# Initialize Azure Search client
search_client = None
try:
    print("Starting initialization of search client...", file=sys.stderr)
    search_client = AzureSearchClient()
    print("Search client initialized successfully", file=sys.stderr)
except Exception as e:
    print(f"Error initializing search client: {str(e)}", file=sys.stderr)
    logger.error(f"Failed to initialize search client: {str(e)}")

# API Endpoints
@app.get("/")
async def root():
    """Root endpoint for health check."""
    return {"message": "Azure AI Search API Server is running", "status": "healthy"}

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    if search_client is None:
        raise HTTPException(status_code=503, detail="Search client not initialized")
    return {"status": "healthy", "search_client": "initialized"}

@app.get("/capabilities")
async def get_search_capabilities():
    """Get information about available search capabilities and configuration."""
    if search_client is None:
        raise HTTPException(status_code=503, detail="Search client not initialized")
    
    try:
        capabilities = {
            "service_info": {
                "endpoint": search_client.endpoint,
                "index": search_client.index_name,
                "authentication": "API Key" if isinstance(search_client.credential, AzureKeyCredential) else "Managed Identity"
            },
            "search_types": [
                {"name": "keyword", "description": "Traditional text-based search using BM25 algorithm"},
                {"name": "vector", "description": "Semantic similarity search using embeddings"},
                {"name": "hybrid", "description": "Combined keyword and vector search with semantic ranking"}
            ],
            "supported_fields": [
                "title", "content", "company", "document_type", 
                "form_type", "ticker", "filing_date", "chunk_id", "source"
            ]
        }
        return capabilities
    except Exception as e:
        logger.error(f"Error getting search capabilities: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting search capabilities: {str(e)}")

@app.post("/search/keyword", response_model=SearchResponse)
async def keyword_search_endpoint(request: SearchRequest):
    """Perform keyword-based search on the Azure AI Search index."""
    if search_client is None:
        raise HTTPException(status_code=503, detail="Search client not initialized")
    
    try:
        # Validate parameters
        top = max(1, min(50, request.top))
        filter_param = request.filters.strip() if request.filters else None
        
        results = search_client.keyword_search(request.query, top, filter_param)
        
        return SearchResponse(
            results=results,
            total_found=len(results),
            search_type="keyword"
        )
    except Exception as e:
        logger.error(f"Error performing keyword search: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error performing keyword search: {str(e)}")

@app.post("/search/vector", response_model=SearchResponse)
async def vector_search_endpoint(request: SearchRequest):
    """Perform vector similarity search on the Azure AI Search index."""
    if search_client is None:
        raise HTTPException(status_code=503, detail="Search client not initialized")
    
    try:
        # Validate parameters
        top = max(1, min(50, request.top))
        filter_param = request.filters.strip() if request.filters else None
        
        results = await search_client.vector_search(request.query, top, "content_vector", filter_param)
        
        return SearchResponse(
            results=results,
            total_found=len(results),
            search_type="vector"
        )
    except Exception as e:
        logger.error(f"Error performing vector search: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error performing vector search: {str(e)}")

@app.post("/search/hybrid", response_model=SearchResponse)
async def hybrid_search_endpoint(request: SearchRequest):
    """Perform hybrid search (keyword + vector) on the Azure AI Search index."""
    if search_client is None:
        raise HTTPException(status_code=503, detail="Search client not initialized")
    
    try:
        # Validate parameters
        top = max(1, min(50, request.top))
        filter_param = request.filters.strip() if request.filters else None
        
        results = await search_client.hybrid_search(request.query, top, "content_vector", filter_param)
        
        return SearchResponse(
            results=results,
            total_found=len(results),
            search_type="hybrid"
        )
    except Exception as e:
        logger.error(f"Error performing hybrid search: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error performing hybrid search: {str(e)}")

if __name__ == "__main__":
    print("Starting HTTP API server...", file=sys.stderr)
    try:
        uvicorn.run(
            app,
            host="0.0.0.0",
            port=SERVER_PORT,
            log_level="info"
        )
    except Exception as e:
        logger.error(f"Error running HTTP API server: {str(e)}")
        print(f"ERROR:__main__:Error running HTTP API server: {str(e)}", file=sys.stderr)
        sys.exit(1)
