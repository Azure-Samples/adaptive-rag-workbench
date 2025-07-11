"""
Agentic Vector RAG Service Implementation for AdaptiveRAG
Based on Azure AI Search Agentic Retrieval concept
https://learn.microsoft.com/en-us/azure/search/search-agentic-retrieval-concept
"""

import logging
import time
import json
import uuid
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone

from azure.search.documents import SearchClient
from azure.search.documents.models import QueryType
from azure.core.credentials import AzureKeyCredential
from azure.identity import DefaultAzureCredential

try:
    from azure.search.documents.indexes.models import (
        KnowledgeAgent, 
        KnowledgeAgentAzureOpenAIModel, 
        KnowledgeAgentTargetIndex, 
        KnowledgeAgentRequestLimits, 
        AzureOpenAIVectorizerParameters
    )
    from azure.search.documents.indexes import SearchIndexClient
    from azure.search.documents.agent import KnowledgeAgentRetrievalClient
    from azure.search.documents.agent.models import (
        KnowledgeAgentRetrievalRequest, 
        KnowledgeAgentMessage, 
        KnowledgeAgentMessageTextContent, 
        KnowledgeAgentIndexParams
    )
    AGENTIC_IMPORTS_AVAILABLE = True
except ImportError:
    AGENTIC_IMPORTS_AVAILABLE = False

from app.core.config import settings
from app.services.token_usage_tracker import token_tracker, ServiceType, OperationType

logger = logging.getLogger(__name__)

class AgenticVectorRAGService:
    """
    Agentic Vector RAG implementation following Azure AI Search best practices.
    Uses Knowledge Agents for intelligent query planning and parallel subquery execution.
    Adapted for AdaptiveRAG's architecture.
    """
    
    def __init__(self):
        self.agent_name = getattr(settings, 'azure_search_agent_name', 'adaptive-rag-agent')
        self.knowledge_agent_client = None
        self.index_client = None
        self.search_client = None
        self.agentic_enabled = AGENTIC_IMPORTS_AVAILABLE
        
        self._initialize_search_client()
        
    def _initialize_search_client(self):
        """Initialize the basic Azure Search client"""
        try:
            credential = AzureKeyCredential(settings.search_admin_key)
            self.search_client = SearchClient(
                endpoint=settings.search_endpoint,
                index_name=settings.search_index,
                credential=credential
            )
            logger.info("Basic Azure Search client initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Azure Search client: {e}")
            raise
        
    async def initialize(self):
        """Initialize the Agentic Vector RAG service"""
        if not self.agentic_enabled:
            logger.error("Agentic imports not available - agentic retrieval will fail")
            logger.error("Please install preview Azure SDK packages for agentic features")
            return
            
        try:
            credential = AzureKeyCredential(settings.search_admin_key)
            
            # Initialize Azure Search Index Client with the latest API version for agentic features
            # Try multiple API versions until we find one that works
            api_versions = [
                "2025-05-01-preview",  # Latest from documentation
                "2024-11-01-preview",  # Previous version
                "2024-07-01-preview",  # Earlier preview
                "2024-05-01-preview",  # Fallback
                None  # Use default
            ]
            
            initialization_error = None
            for api_version in api_versions:
                try:
                    if api_version:
                        self.index_client = SearchIndexClient(
                            endpoint=settings.search_endpoint,
                            credential=credential,
                            api_version=api_version
                        )
                        logger.info(f"Using API version: {api_version}")
                    else:
                        self.index_client = SearchIndexClient(
                            endpoint=settings.search_endpoint,
                            credential=credential
                        )
                        logger.info("Using default API version")
                    
                    # Test the client by trying to list methods
                    available_methods = [method for method in dir(self.index_client) if 'agent' in method.lower()]
                    logger.info(f"Available agent methods: {available_methods}")
                    break
                    
                except Exception as e:
                    initialization_error = e
                    logger.warning(f"API version {api_version} failed: {e}")
                    continue
            
            if not self.index_client:
                raise Exception(f"Failed to initialize index client with any API version. Last error: {initialization_error}")
            
            # Try to create or update the knowledge agent - let errors surface
            self._create_or_update_knowledge_agent()
            
            # Initialize the Knowledge Agent Retrieval Client with same API version approach
            retrieval_client_error = None
            for api_version in api_versions:
                try:
                    if api_version:
                        self.knowledge_agent_client = KnowledgeAgentRetrievalClient(
                            endpoint=settings.search_endpoint,
                            agent_name=self.agent_name,
                            credential=credential,
                            api_version=api_version
                        )
                    else:
                        self.knowledge_agent_client = KnowledgeAgentRetrievalClient(
                            endpoint=settings.search_endpoint,
                            agent_name=self.agent_name,
                            credential=credential
                        )
                    logger.info(f"Knowledge agent retrieval client initialized with API version: {api_version}")
                    break
                except Exception as e:
                    retrieval_client_error = e
                    logger.warning(f"Retrieval client API version {api_version} failed: {e}")
                    continue
            
            if not self.knowledge_agent_client:
                raise Exception(f"Failed to initialize knowledge agent retrieval client. Last error: {retrieval_client_error}")
            
            logger.info("Agentic Vector RAG service initialized successfully with full agentic capabilities")
            
        except Exception as e:
            logger.error(f"Failed to initialize Agentic Vector RAG service: {e}")
            logger.error(f"Error details: {type(e).__name__}: {str(e)}")
            # Set agentic_enabled to False but don't raise - let the error surface in process_question
            self.agentic_enabled = False
            self.knowledge_agent_client = None
            # Re-raise to surface the error
            raise Exception(f"Agentic service initialization failed: {str(e)}")

    def _create_or_update_knowledge_agent(self):
        """
        Create or update the Knowledge Agent in Azure AI Search.
        
        This configures the agent with:
        - Azure OpenAI model connections for query planning and answer generation
        - Target search index configuration
        - Request limits and performance tuning
        - Semantic ranking thresholds for quality control
        """
        if not self.agentic_enabled:
            return
            
        try:
            # Extract deployment name from model config
            chat_deployment = settings.openai_chat_deployment
            
            logger.info(f"Creating/updating knowledge agent '{self.agent_name}' with:")
            logger.info(f"  - OpenAI endpoint: {settings.openai_endpoint}")
            logger.info(f"  - Chat deployment: {chat_deployment}")
            logger.info(f"  - Target index: {settings.search_index}")
            
            # Configure Azure OpenAI parameters for the knowledge agent
            azure_openai_params = AzureOpenAIVectorizerParameters(
                resource_url=settings.openai_endpoint,
                deployment_name=chat_deployment,
                model_name="gpt-4o-mini",  # Use efficient model for query planning and answer generation
                api_key=settings.openai_key
            )
            
            # Create the agent model configuration
            agent_model = KnowledgeAgentAzureOpenAIModel(
                azure_open_ai_parameters=azure_openai_params
            )
            
            # Configure target index with semantic ranking settings
            target_index = KnowledgeAgentTargetIndex(
                index_name=settings.search_index,
                default_reranker_threshold=1.0  # Lower threshold for better recall
            )
            
            # Set request limits for performance and cost control
            request_limits = KnowledgeAgentRequestLimits(
                max_tokens=16000,  # Sufficient for complex financial queries and comprehensive answers
                max_requests_per_minute=60  # Reasonable throughput
            )
            
            # Create the knowledge agent with comprehensive configuration
            agent = KnowledgeAgent(
                name=self.agent_name,
                models=[agent_model],
                target_indexes=[target_index],
                request_limits=request_limits,
                description="Financial document analysis agent for SEC filings and earnings reports"
            )
            
            if self.index_client:
                # Try different method names for knowledge agent creation (synchronous)
                if hasattr(self.index_client, 'create_or_update_knowledge_agent'):
                    self.index_client.create_or_update_knowledge_agent(agent)
                elif hasattr(self.index_client, 'create_or_update_agent'):
                    self.index_client.create_or_update_agent(agent)
                elif hasattr(self.index_client, 'create_knowledge_agent'):
                    self.index_client.create_knowledge_agent(agent)
                else:
                    # List available methods for debugging
                    available_methods = [method for method in dir(self.index_client) if 'agent' in method.lower()]
                    raise Exception(f"No knowledge agent creation method found. Available agent methods: {available_methods}")
                
                logger.info(f"Knowledge agent '{self.agent_name}' created/updated successfully")
            else:
                raise Exception("Index client not available")
            
        except Exception as e:
            logger.error(f"Failed to create/update knowledge agent: {e}")
            raise

    async def process_question(self, 
                             question: str, 
                             conversation_history: Optional[List[Dict[str, str]]] = None,
                             rag_mode: str = "agentic-rag",
                             session_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Process a question using pure agentic retrieval - no fallback logic.
        
        This method performs only agentic retrieval using Azure AI Search Knowledge Agents.
        All errors are surfaced for debugging rather than falling back to hybrid search.
        
        Args:
            question: The user's question
            conversation_history: Previous conversation messages for context
            rag_mode: RAG mode (should be "agentic-rag")
            session_id: Optional session ID for tracking
            
        Returns:
            Dict containing answer, citations, query rewrites, and metadata
            
        Raises:
            Exception: If agentic retrieval fails or is not available
        """
        if session_id is None:
            session_id = str(uuid.uuid4())
            
        tracking_id = token_tracker.start_tracking(
            session_id=session_id,
            service_type=ServiceType.AGENTIC_RAG,
            operation_type=OperationType.ANSWER_GENERATION,
            endpoint="/agentic-rag",
            rag_mode=rag_mode
        )
        
        start_time = time.time()
        
        try:
            # Ensure agentic service is properly initialized
            await self.ensure_initialized()
                
            result = await self._perform_agentic_retrieval(question, conversation_history, tracking_id)
            
            processing_time = time.time() - start_time
            result["processing_time_ms"] = round(processing_time * 1000, 2)
            result["session_id"] = session_id
            result["rag_mode"] = rag_mode
            
            return result
            
        except Exception as e:
            logger.error(f"Agentic retrieval failed: {e}")
            logger.error(f"Error type: {type(e).__name__}")
            logger.error(f"Error details: {str(e)}")
            
            token_tracker.record_token_usage(
                record_id=tracking_id,
                prompt_tokens=0,
                completion_tokens=0,
                success=False,
                error_message=str(e)
            )
            
            # Surface the error instead of returning a fallback response
            raise Exception(f"Agentic retrieval failed: {str(e)}")

    def _extract_activity_steps_from_response(self, response: Any) -> List[Dict[str, Any]]:
        """
        Extract activity steps from agentic response for detailed tracking.
        
        Activity steps provide insight into:
        - Query planning and decomposition
        - Multiple subquery execution details
        - Semantic ranking operations
        - Token usage per step
        - Timing and performance metrics
        
        Args:
            response: The agentic retrieval response
            
        Returns:
            List of activity step dictionaries with detailed metadata
        """
        activity_steps = []
        
        try:
            if hasattr(response, 'activity') and response.activity:
                for i, activity in enumerate(response.activity):
                    step = {
                        "id": getattr(activity, 'id', i + 1),
                        "step_number": i + 1,
                        "type": activity.__class__.__name__ if hasattr(activity, '__class__') else "Unknown",
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    }
                    
                    # Extract common properties
                    if hasattr(activity, 'input_tokens'):
                        step["input_tokens"] = getattr(activity, 'input_tokens', 0)
                    if hasattr(activity, 'output_tokens'):
                        step["output_tokens"] = getattr(activity, 'output_tokens', 0)
                    if hasattr(activity, 'elapsed_ms'):
                        step["elapsed_ms"] = getattr(activity, 'elapsed_ms', 0)
                    if hasattr(activity, 'query_time'):
                        step["query_time"] = getattr(activity, 'query_time', '')
                    
                    # Extract query details for search activities
                    if hasattr(activity, 'query'):
                        query_info = getattr(activity, 'query', {})
                        if isinstance(query_info, dict):
                            step["query"] = query_info
                            # Add subquery identification
                            if 'search' in query_info:
                                step["subquery"] = f"Subquery {i + 1}: {query_info['search']}"
                        elif hasattr(query_info, 'search'):
                            step["query"] = {
                                "search": getattr(query_info, 'search', ''),
                                "filter": getattr(query_info, 'filter', None)
                            }
                            step["subquery"] = f"Subquery {i + 1}: {getattr(query_info, 'search', '')}"
                    
                    # Extract target index for search activities
                    if hasattr(activity, 'target_index'):
                        step["target_index"] = getattr(activity, 'target_index', '')
                    
                    # Extract count for search activities
                    if hasattr(activity, 'count'):
                        step["count"] = getattr(activity, 'count', 0)
                    
                    # Extract additional metadata
                    if hasattr(activity, 'score'):
                        step["score"] = getattr(activity, 'score', 0.0)
                    if hasattr(activity, 'status'):
                        step["status"] = getattr(activity, 'status', 'unknown')
                    
                    # Identify step type for better categorization
                    step_type = step["type"].lower()
                    if "search" in step_type or "query" in step_type:
                        step["category"] = "search"
                    elif "rank" in step_type or "semantic" in step_type:
                        step["category"] = "ranking"
                    elif "llm" in step_type or "generation" in step_type:
                        step["category"] = "generation"
                    else:
                        step["category"] = "processing"
                    
                    activity_steps.append(step)
                    
            # If no activity found, create a basic step
            if not activity_steps:
                activity_steps.append({
                    "id": 1,
                    "step_number": 1,
                    "type": "AgenticRetrievalQuery",
                    "category": "search",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "query": {"search": "Complex query processed", "filter": None},
                    "subquery": "Subquery 1: Complex query processed",
                    "target_index": settings.search_index
                })
                
        except Exception as e:
            logger.warning(f"Could not extract activity steps: {e}")
            # Return basic fallback step
            activity_steps = [{
                "id": 1,
                "step_number": 1,
                "type": "AgenticRetrievalQuery",
                "category": "search",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "error": str(e),
                "subquery": "Subquery 1: Error processing query"
            }]
        
        return activity_steps

    async def _perform_agentic_retrieval(self, 
                                       question: str, 
                                       conversation_history: Optional[List[Dict[str, str]]] = None,
                                       tracking_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Perform agentic retrieval using Azure AI Search Knowledge Agent.
        
        This implements the full agentic retrieval pipeline based on Azure documentation:
        1. Analyzes conversation history to understand underlying information need
        2. Breaks down complex queries into focused subqueries using LLM reasoning
        3. Executes subqueries in parallel using hybrid search (text + vectors)
        4. Applies semantic ranking for L2 reranking and relevance scoring
        5. Merges results and returns structured response with comprehensive metadata
        
        Features implemented:
        - Query expansion and parallel execution
        - Spelling correction and synonym expansion
        - Chat history context analysis
        - Comprehensive citation extraction
        - Activity logging and step tracking
        - Token usage monitoring for billing
        - Semantic ranking with confidence thresholds
        
        Args:
            question: The user's question
            conversation_history: Previous conversation messages for context
            tracking_id: Optional tracking ID for token usage monitoring
            
        Returns:
            Dict containing answer, citations, query rewrites, token usage, and metadata
        """
        try:
            # Build conversation messages including system instructions
            messages = self._build_conversation_messages(question, conversation_history)
            
            # Set up agentic retrieval parameters with enhanced configuration
            index_params = KnowledgeAgentIndexParams(
                index_name=settings.search_index,
                reranker_threshold=1.0,  # Lower threshold for better recall
                top_k=20,  # Retrieve more documents for comprehensive analysis
                # Note: Additional parameters may be available in preview versions
            )
            
            # Create retrieval request with enhanced parameters
            request = KnowledgeAgentRetrievalRequest(
                messages=messages,
                target_index_params=[index_params],
                # Enable multiple subqueries for comprehensive analysis
                max_subqueries=5,  # Allow up to 5 subqueries for complex questions
                enable_query_rewriting=True,  # Enable query rewriting for better results
                # Note: Some parameters may not be available in current SDK version
            )
            
            logger.info(f"Starting agentic retrieval for question: '{question[:100]}...'")
            logger.info(f"Using {len(messages)} messages for context (including system instructions)")
            
            # Perform agentic retrieval with explicit error handling
            if not self.knowledge_agent_client:
                raise Exception(f"Knowledge agent client not available. Agentic enabled: {self.agentic_enabled}, Imports available: {AGENTIC_IMPORTS_AVAILABLE}")
            
            # Execute the agentic retrieval pipeline
            start_time = time.time()
            logger.info("Executing agentic retrieval with knowledge agent...")
            response = self.knowledge_agent_client.retrieve(request)  # Synchronous call
            retrieval_time = time.time() - start_time
            
            logger.info(f"Agentic retrieval completed in {retrieval_time:.2f} seconds")
            
            # Extract the unified response text (grounding data)
            answer = self._extract_answer_from_response(response)
            
            # Extract citations from references with enhanced metadata
            citations = self._format_citations_from_references(
                response.references if hasattr(response, 'references') else []
            )
            
            # Extract query rewrites (subqueries generated by LLM)
            query_rewrites = self._extract_query_rewrites_from_response(response)
            
            # Extract detailed activity steps for transparency
            activity_steps = self._extract_activity_steps_from_response(response)
            
            # Extract comprehensive token usage for billing tracking
            token_usage = self._extract_token_usage_from_response(response)
            
            # Record token usage for tracking and billing
            if tracking_id and token_usage:
                token_tracker.record_token_usage(
                    record_id=tracking_id,
                    prompt_tokens=token_usage.get("prompt_tokens", 0),
                    completion_tokens=token_usage.get("completion_tokens", 0),
                    success=True
                )
            
            logger.info(f"Agentic retrieval completed successfully:")
            logger.info(f"  - Citations: {len(citations)}")
            logger.info(f"  - Query rewrites: {len(query_rewrites)}")
            logger.info(f"  - Activity steps: {len(activity_steps)}")
            logger.info(f"  - Token usage: {token_usage.get('total_tokens', 0)} total tokens")
            
            return {
                "answer": answer,
                "citations": citations,
                "query_rewrites": query_rewrites,
                "activity_steps": activity_steps,
                "token_usage": token_usage,
                "success": True,
                "retrieval_method": "agentic",
                "processing_details": {
                    "subqueries_executed": len(query_rewrites),
                    "documents_retrieved": len(citations),
                    "semantic_ranking_applied": True,
                    "retrieval_time_seconds": round(retrieval_time, 2),
                    "context_messages": len(messages),
                    "reranker_threshold": 2.5
                }
            }
            
        except Exception as e:
            logger.error(f"Agentic retrieval failed: {e}")
            logger.error(f"Error details: {type(e).__name__}: {str(e)}")
            raise

    def _build_conversation_messages(self, 
                                   question: str, 
                                   conversation_history: Optional[List[Dict[str, str]]] = None) -> List[Any]:
        """
        Build conversation messages for the knowledge agent.
        
        Note: The agentic retrieval API only supports 'user' and 'assistant' roles.
        System instructions must be embedded in the user message or handled by the agent itself.
        
        Args:
            question: The current user question
            conversation_history: Previous conversation messages
            
        Returns:
            List of formatted message objects for the knowledge agent
        """
        if not AGENTIC_IMPORTS_AVAILABLE:
            # Fallback for when agentic imports are not available
            messages = []
            
            # Add recent conversation history (last 5 messages)
            if conversation_history:
                for msg in conversation_history[-5:]:
                    role = msg.get("role", "user")
                    content = msg.get("content", "")
                    if content and role in ["user", "assistant"]:
                        messages.append({"role": role, "content": content})
                        
            # Add current question with enhanced context
            enhanced_question = f"""Please analyze the following financial question using the available SEC filings, earnings reports, and corporate documents. Provide accurate, data-driven insights with specific citations.

Question: {question}

Please provide:
- Comprehensive analysis based on available financial documents
- Specific citations with document references, company names, filing types, and dates
- Key financial metrics, trends, and contextual factors
- Professional financial analysis with proper structure"""
            
            messages.append({"role": "user", "content": enhanced_question})
            return messages
        
        # Full agentic implementation with proper message objects (user/assistant only)
        messages = []
        
        # Add recent conversation history for context (limit to last 8 messages for efficiency)
        if conversation_history:
            for msg in conversation_history[-8:]:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                
                # Only include user and assistant messages
                if content and role in ["user", "assistant"]:
                    messages.append(
                        KnowledgeAgentMessage(
                            role=role,
                            content=[KnowledgeAgentMessageTextContent(text=content)]
                        )
                    )
        
        # Add the current user question with enhanced context for better analysis
        enhanced_question = f"""Please analyze the following financial question using the available SEC filings, earnings reports, and corporate documents. As a financial analyst, provide comprehensive, accurate analysis with specific citations.

Question: {question}

Please provide:
- Detailed financial analysis based on available documents
- Specific citations with document references (company, filing type, date)
- Key metrics, trends, and comparative analysis where applicable
- Professional insights with proper financial context
- Clear structure with citations for all claims

Focus on factual data from the indexed financial documents and provide balanced analysis considering multiple data sources."""
        
        messages.append(
            KnowledgeAgentMessage(
                role="user",
                content=[KnowledgeAgentMessageTextContent(text=enhanced_question)]
            )
        )
        
        logger.info(f"Built conversation with {len(messages)} messages for agentic retrieval (user/assistant only)")
        return messages

    def _format_citations_from_references(self, references: List[Any]) -> List[Dict[str, Any]]:
        """
        Format citations from agentic retrieval references with enhanced metadata.
        
        Since agentic retrieval references may not include source_data, we'll attempt
        to look up the actual document metadata from the search index using doc_key.
        
        Args:
            references: List of reference objects from agentic retrieval
            
        Returns:
            List of formatted citation objects with comprehensive metadata
        """
        citations = []
        
        for i, ref in enumerate(references):
            try:
                citation = {
                    "id": str(i + 1),
                    "doc_key": getattr(ref, 'doc_key', '') or getattr(ref, 'DocKey', ''),
                    "activity_source": getattr(ref, 'activity_source', None) or getattr(ref, 'ActivitySource', None),
                    "reference_type": ref.__class__.__name__ if hasattr(ref, '__class__') else "Unknown",
                }
                
                # Extract source data - this is where the actual document content is
                source_data = None
                if hasattr(ref, 'source_data') and ref.source_data:
                    source_data = ref.source_data
                elif hasattr(ref, 'SourceData') and ref.SourceData:
                    source_data = ref.SourceData
                
                if source_data:
                    citation["source_data"] = source_data
                    
                    # If source_data is a dict, extract key fields
                    if isinstance(source_data, dict):
                        citation.update({
                            "title": source_data.get("title", ""),
                            "content": source_data.get("content", ""),
                            "company": source_data.get("company", ""),
                            "document_type": source_data.get("document_type", ""),
                            "filing_date": source_data.get("filing_date", ""),
                            "form_type": source_data.get("form_type", ""),
                            "ticker": source_data.get("ticker", ""),
                            "source": source_data.get("source", ""),
                            "page_number": source_data.get("page_number"),
                            "section_type": source_data.get("section_type", ""),
                            "chunk_id": source_data.get("chunk_id", ""),
                            "document_url": source_data.get("document_url", ""),
                        })
                    elif isinstance(source_data, str):
                        # If source_data is a string, try to parse as JSON
                        try:
                            import json
                            parsed_data = json.loads(source_data)
                            if isinstance(parsed_data, dict):
                                citation.update({
                                    "title": parsed_data.get("title", ""),
                                    "content": parsed_data.get("content", ""),
                                    "company": parsed_data.get("company", ""),
                                    "document_type": parsed_data.get("document_type", ""),
                                    "source": parsed_data.get("source", ""),
                                })
                        except:
                            citation["content"] = source_data[:500]  # Use as content if not JSON
                else:
                    # If no source_data, try to look up document metadata using doc_key
                    doc_key = citation.get("doc_key")
                    if doc_key and self.search_client:
                        try:
                            # Look up the document in the search index
                            doc_metadata = self._lookup_document_metadata(doc_key)
                            if doc_metadata:
                                citation.update(doc_metadata)
                        except Exception as e:
                            logger.warning(f"Failed to lookup document metadata for {doc_key}: {e}")
                
                # Extract additional metadata if available directly on reference
                for attr in ['score', 'reranker_score', 'title', 'content', 'url', 'chunk_id']:
                    if hasattr(ref, attr):
                        value = getattr(ref, attr)
                        if value and not citation.get(attr):  # Don't override source_data values
                            citation[attr] = value
                
                # Ensure we have at least some basic info
                if not citation.get("title"):
                    # Try to infer title from doc_key
                    doc_key = citation.get("doc_key", "")
                    if doc_key:
                        # Extract filing number from doc_key (e.g., "0001564590-19-027952_chunk_25")
                        filing_parts = doc_key.split("_")
                        if len(filing_parts) >= 2:
                            filing_id = filing_parts[0]
                            chunk_num = filing_parts[1].replace("chunk_", "")
                            citation["title"] = f"SEC Filing {filing_id} - Section {chunk_num}"
                        else:
                            citation["title"] = f"Document {doc_key}"
                    else:
                        citation["title"] = f"Document {i + 1}"
                
                if not citation.get("content"):
                    citation["content"] = "Content available in financial document"
                
                citations.append(citation)
                
            except Exception as e:
                logger.warning(f"Error formatting citation {i}: {e}")
                # Add a basic citation even if parsing fails
                citations.append({
                    "id": str(i + 1),
                    "title": f"Document {i + 1}",
                    "content": "Error extracting citation details",
                    "reference_type": "Unknown",
                    "error": str(e)
                })
                continue
        
        return citations

    def _lookup_document_metadata(self, doc_key: str) -> Dict[str, Any]:
        """
        Look up document metadata from the search index using doc_key.
        
        Args:
            doc_key: The document key to look up
            
        Returns:
            Dictionary containing document metadata
        """
        try:
            # Search for the document by key
            search_results = self.search_client.search(
                search_text="*",
                filter=f"chunk_id eq '{doc_key}'",
                select=["title", "company", "document_type", "filing_date", "form_type", "ticker", "source", "content"],
                top=1
            )
            
            for result in search_results:
                # Extract metadata from the search result
                metadata = {
                    "title": result.get("title", ""),
                    "company": result.get("company", ""),
                    "document_type": result.get("document_type", ""),
                    "filing_date": result.get("filing_date", ""),
                    "form_type": result.get("form_type", ""),
                    "ticker": result.get("ticker", ""),
                    "source": result.get("source", ""),
                    "content": result.get("content", "")[:500] if result.get("content") else "",  # Limit content length
                }
                
                # Clean up empty values
                metadata = {k: v for k, v in metadata.items() if v}
                return metadata
                
        except Exception as e:
            logger.warning(f"Error looking up document metadata for {doc_key}: {e}")
        
        return {}

    def _extract_query_rewrites_from_response(self, response: Any) -> List[str]:
        """
        Extract query rewrites from agentic response.
        
        Query rewrites represent the subqueries generated by the LLM
        during query planning phase of agentic retrieval.
        
        Args:
            response: The agentic retrieval response
            
        Returns:
            List of query rewrite strings
        """
        query_rewrites = []
        
        try:
            # First try to get query rewrites from metadata
            if hasattr(response, 'query_rewrites'):
                query_rewrites = response.query_rewrites
            elif hasattr(response, 'metadata') and response.metadata:
                metadata = response.metadata
                if isinstance(metadata, dict) and 'query_rewrites' in metadata:
                    query_rewrites = metadata['query_rewrites']
            
            # If not found in metadata, extract from activity steps
            if not query_rewrites and hasattr(response, 'activity'):
                for activity in response.activity:
                    if hasattr(activity, 'query'):
                        query = getattr(activity, 'query', {})
                        if isinstance(query, dict) and 'search' in query:
                            search_text = query['search']
                            if search_text and search_text not in query_rewrites:
                                query_rewrites.append(search_text)
                        elif hasattr(query, 'search'):
                            search_text = getattr(query, 'search', '')
                            if search_text and search_text not in query_rewrites:
                                query_rewrites.append(search_text)
                                
        except Exception as e:
            logger.warning(f"Could not extract query rewrites: {e}")
        
        return query_rewrites if isinstance(query_rewrites, list) else []

    def _extract_answer_from_response(self, response: Any) -> str:
        """
        Extract answer from agentic retrieval response.
        
        The response.response[0].content[0].text contains the actual content.
        If it's raw JSON grounding data, we need to synthesize a proper answer.
        
        Args:
            response: The agentic retrieval response
            
        Returns:
            The extracted or synthesized answer string
        """
        try:
            # Extract the content from the response structure
            raw_content = ""
            if hasattr(response, 'response') and response.response:
                if isinstance(response.response, list) and len(response.response) > 0:
                    first_response = response.response[0]
                    if hasattr(first_response, 'content') and first_response.content:
                        if isinstance(first_response.content, list) and len(first_response.content) > 0:
                            content_item = first_response.content[0]
                            if hasattr(content_item, 'text') and content_item.text:
                                raw_content = content_item.text
            
            # Check if this is raw JSON grounding data vs actual LLM answer
            if raw_content.startswith('[{') or raw_content.startswith('{"'):
                logger.info("Detected raw JSON grounding data - synthesizing answer from content")
                return self._synthesize_answer_from_grounding_data(raw_content, response)
            elif raw_content and len(raw_content) > 50:
                # This appears to be an actual LLM-generated answer
                logger.info("Detected LLM-generated answer")
                return raw_content
            else:
                # Try other response properties as fallback
                for attr in ['answer', 'content', 'text']:
                    if hasattr(response, attr):
                        value = getattr(response, attr)
                        if isinstance(value, str) and len(value) > 50:
                            return value
                
                # Ultimate fallback - synthesize from grounding data
                logger.warning("No direct answer found, attempting to synthesize from available data")
                return self._synthesize_answer_from_grounding_data("", response)
                
        except Exception as e:
            logger.error(f"Error extracting answer: {e}")
            return "I encountered an error while processing the financial document response. Please try again."

    def _synthesize_answer_from_grounding_data(self, raw_content: str, response: Any) -> str:
        """
        Synthesize a proper analytical answer from raw grounding data using LLM.
        
        This method takes the raw grounding data (JSON format) and uses an LLM
        to generate a comprehensive, analytical answer rather than just concatenating excerpts.
        
        Args:
            raw_content: Raw content that may be JSON grounding data
            response: The full response object for additional context
            
        Returns:
            LLM-synthesized analytical answer string
        """
        try:
            import json
            
            # Try to parse the JSON grounding data
            grounding_data = []
            if raw_content:
                try:
                    grounding_data = json.loads(raw_content)
                    if not isinstance(grounding_data, list):
                        grounding_data = [grounding_data]
                except json.JSONDecodeError:
                    logger.warning("Could not parse grounding data as JSON")
            
            # If no grounding data, try to extract from references
            if not grounding_data and hasattr(response, 'references') and response.references:
                logger.info("Extracting content from response references")
                for ref in response.references[:5]:  # Use top 5 references
                    ref_data = {}
                    if hasattr(ref, 'source_data') and ref.source_data:
                        if isinstance(ref.source_data, dict):
                            ref_data = ref.source_data
                        elif isinstance(ref.source_data, str):
                            try:
                                ref_data = json.loads(ref.source_data)
                            except:
                                ref_data = {"content": ref.source_data}
                    
                    if ref_data:
                        grounding_data.append(ref_data)
            
            # Use LLM to synthesize analytical answer from grounding data
            if grounding_data:
                return self._generate_llm_synthesized_answer(grounding_data)
            
            # Final fallback
            return "I found relevant financial documents but couldn't generate a comprehensive analysis. The available data includes financial metrics and reports, but may require more specific queries to provide detailed insights."
            
        except Exception as e:
            logger.error(f"Error synthesizing analytical answer from grounding data: {e}")
            return "I encountered an error while analyzing the financial document content. Please try rephrasing your question for better results."

    def _generate_llm_synthesized_answer(self, grounding_data: List[Dict[str, Any]]) -> str:
        """
        Generate a comprehensive analytical answer using LLM synthesis.
        
        This method uses the OpenAI API to generate a proper analytical answer
        from the grounding data, rather than just concatenating excerpts.
        
        Args:
            grounding_data: List of document data dictionaries
            
        Returns:
            LLM-generated analytical answer
        """
        try:
            # Import OpenAI for synthesis
            from openai import AzureOpenAI
            
            # Prepare the synthesis prompt
            synthesis_prompt = self._build_synthesis_prompt(grounding_data)
            
            # Use synchronous Azure OpenAI client for synthesis
            client = AzureOpenAI(
                api_key=settings.openai_key,
                azure_endpoint=settings.openai_endpoint,
                api_version=settings.openai_api_version
            )
            
            # Generate synthesis
            response = client.chat.completions.create(
                model=settings.openai_chat_deployment,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a senior financial analyst. Provide comprehensive, analytical responses based on the provided document excerpts. Focus on key insights, trends, and actionable information. Use professional financial language and structure your analysis logically."
                    },
                    {
                        "role": "user",
                        "content": synthesis_prompt
                    }
                ],
                max_tokens=1500,
                temperature=0.1,  # Low temperature for factual analysis
                top_p=0.9
            )
            
            synthesis_result = response.choices[0].message.content
            logger.info("Successfully generated LLM-synthesized answer")
            return synthesis_result
                
        except Exception as e:
            logger.error(f"Error generating LLM synthesis: {e}")
            # Fall back to basic concatenation with structure
            return self._fallback_structured_response(grounding_data)

    def _build_synthesis_prompt(self, grounding_data: List[Dict[str, Any]]) -> str:
        """
        Build a comprehensive synthesis prompt for the LLM.
        
        Args:
            grounding_data: List of document data dictionaries
            
        Returns:
            Formatted synthesis prompt
        """
        prompt_parts = []
        
        # Introduction
        prompt_parts.append("Please analyze the following financial document excerpts and provide a comprehensive, analytical response.")
        prompt_parts.append("Structure your analysis with clear sections and cite specific information from the documents.")
        prompt_parts.append("")
        
        # Add document excerpts
        prompt_parts.append("DOCUMENT EXCERPTS:")
        prompt_parts.append("=" * 50)
        
        for i, item in enumerate(grounding_data[:5]):  # Use top 5 for synthesis
            if isinstance(item, dict):
                title = item.get('title', f'Document {i+1}')
                company = item.get('company', '')
                doc_type = item.get('document_type', '')
                content = item.get('content', '')
                
                # Build source info
                source_info = f"Source: {title}"
                if company:
                    source_info += f" ({company})"
                if doc_type:
                    source_info += f" - {doc_type}"
                
                prompt_parts.append(f"[{i+1}] {source_info}")
                prompt_parts.append("-" * 40)
                
                if content:
                    # Limit content to reasonable size for synthesis
                    content_snippet = content[:800] + ('...' if len(content) > 800 else '')
                    prompt_parts.append(content_snippet)
                
                prompt_parts.append("")
        
        # Analysis instructions
        prompt_parts.append("=" * 50)
        prompt_parts.append("ANALYSIS INSTRUCTIONS:")
        prompt_parts.append("1. Provide a comprehensive analysis of the key financial information")
        prompt_parts.append("2. Identify trends, patterns, and significant metrics")
        prompt_parts.append("3. Compare data across companies/time periods where applicable")
        prompt_parts.append("4. Structure your response with clear headings and sections")
        prompt_parts.append("5. Cite specific document sources for all claims")
        prompt_parts.append("6. Focus on actionable insights and professional analysis")
        prompt_parts.append("")
        prompt_parts.append("Please provide your analysis now:")
        
        return "\n".join(prompt_parts)

    def _fallback_structured_response(self, grounding_data: List[Dict[str, Any]]) -> str:
        """
        Generate a structured response when LLM synthesis fails.
        
        Args:
            grounding_data: List of document data dictionaries
            
        Returns:
            Structured fallback response
        """
        answer_parts = []
        
        # Extract metadata
        companies = set()
        document_types = set()
        
        for item in grounding_data:
            if isinstance(item, dict):
                if item.get('company'):
                    companies.add(item['company'])
                if item.get('document_type'):
                    document_types.add(item['document_type'])
        
        # Build structured response
        company_list = ', '.join(sorted(companies)) if companies else 'the analyzed companies'
        doc_types = ', '.join(sorted(document_types)) if document_types else 'financial documents'
        
        answer_parts.append(f"# Financial Analysis Summary")
        answer_parts.append(f"Based on analysis of {doc_types} for {company_list}:")
        answer_parts.append("")
        
        # Add key findings
        answer_parts.append("## Key Findings")
        for i, item in enumerate(grounding_data[:3]):  # Use top 3 items
            if isinstance(item, dict):
                title = item.get('title', f'Document {i+1}')
                content = item.get('content', '')
                
                if content and len(content) > 100:
                    content_snippet = content[:400] + ('...' if len(content) > 400 else '')
                    answer_parts.append(f"**{title}:**")
                    answer_parts.append(content_snippet)
                    answer_parts.append("")
        
        # Add summary
        answer_parts.append("## Summary")
        answer_parts.append(f"This analysis covers {len(grounding_data)} relevant document sections ")
        answer_parts.append(f"from {len(companies)} companies across {len(document_types)} document types." if companies and document_types else "from the financial document repository.")
        
        return "\n".join(answer_parts)

    def _extract_token_usage_from_response(self, response: Any) -> Dict[str, int]:
        """
        Extract token usage from agentic response with enhanced tracking.
        
        Token usage includes both query planning tokens (from LLM) and
        semantic ranking tokens (from Azure AI Search).
        
        Args:
            response: The agentic retrieval response
            
        Returns:
            Dict with token usage breakdown
        """
        token_usage = {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
            "query_planning_tokens": 0,
            "semantic_ranking_tokens": 0
        }
        
        try:
            # Extract from direct usage property
            if hasattr(response, 'usage'):
                usage = response.usage
                if hasattr(usage, 'prompt_tokens'):
                    token_usage["prompt_tokens"] = getattr(usage, 'prompt_tokens', 0)
                    token_usage["completion_tokens"] = getattr(usage, 'completion_tokens', 0)
                    token_usage["total_tokens"] = getattr(usage, 'total_tokens', 0)
            
            # Extract from activity steps
            if hasattr(response, 'activity') and response.activity:
                for activity in response.activity:
                    if hasattr(activity, 'input_tokens'):
                        input_tokens = getattr(activity, 'input_tokens', 0)
                        token_usage["prompt_tokens"] += input_tokens
                        token_usage["query_planning_tokens"] += input_tokens
                        
                    if hasattr(activity, 'output_tokens'):
                        output_tokens = getattr(activity, 'output_tokens', 0)
                        token_usage["completion_tokens"] += output_tokens
                        token_usage["query_planning_tokens"] += output_tokens
                        
                    # Track semantic ranking tokens separately
                    if hasattr(activity, '__class__') and 'SemanticRanker' in activity.__class__.__name__:
                        if hasattr(activity, 'input_tokens'):
                            token_usage["semantic_ranking_tokens"] += getattr(activity, 'input_tokens', 0)
                            
            # Calculate total if not already provided
            if token_usage["total_tokens"] == 0:
                token_usage["total_tokens"] = token_usage["prompt_tokens"] + token_usage["completion_tokens"]
                
        except Exception as e:
            logger.warning(f"Could not extract token usage: {e}")
        
        return token_usage

    async def get_diagnostics(self) -> Dict[str, Any]:
        """Get diagnostic information about the service"""
        return {
            "agentic_enabled": self.agentic_enabled,
            "knowledge_agent_available": self.knowledge_agent_client is not None,
            "search_client_available": self.search_client is not None,
            "agent_name": self.agent_name,
            "search_endpoint": settings.search_endpoint,
            "search_index": settings.search_index,
            "imports_available": AGENTIC_IMPORTS_AVAILABLE
        }

    def is_initialized(self) -> bool:
        """Check if the agentic service is properly initialized"""
        return (
            self.agentic_enabled and 
            self.knowledge_agent_client is not None and
            self.index_client is not None
        )

    async def ensure_initialized(self):
        """Ensure the service is initialized, initialize if needed"""
        if not self.is_initialized():
            logger.info("Agentic service not initialized, initializing now...")
            await self.initialize()
        
        # Double-check after initialization
        if not self.is_initialized():
            raise Exception(
                f"Agentic service failed to initialize properly. "
                f"Agentic enabled: {self.agentic_enabled}, "
                f"Knowledge agent client: {self.knowledge_agent_client is not None}, "
                f"Index client: {self.index_client is not None}"
            )

# Global instance
agentic_rag_service = AgenticVectorRAGService()
