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
            logger.warning("Agentic imports not available, running in basic mode")
            return
            
        try:
            credential = AzureKeyCredential(settings.search_admin_key)
            
            # Initialize Azure Search Index Client with the latest API version for agentic features
            self.index_client = SearchIndexClient(
                endpoint=settings.search_endpoint,
                credential=credential,
                api_version="2024-11-01-preview"  # Latest stable API version for agentic features
            )
            
            # Try to create or update the knowledge agent
            try:
                await self._create_or_update_knowledge_agent()
                
                # Initialize the Knowledge Agent Retrieval Client
                self.knowledge_agent_client = KnowledgeAgentRetrievalClient(
                    endpoint=settings.search_endpoint,
                    agent_name=self.agent_name,
                    credential=credential,
                    api_version="2024-11-01-preview"
                )
                
                logger.info("Agentic Vector RAG service initialized successfully with full agentic capabilities")
                
            except Exception as agent_error:
                logger.warning(f"Failed to initialize knowledge agent: {agent_error}")
                logger.warning("Agentic Vector RAG will operate in fallback mode without knowledge agent")
                self.knowledge_agent_client = None
            
        except Exception as e:
            logger.error(f"Failed to initialize Agentic Vector RAG service: {e}")
            self.agentic_enabled = False

    async def _create_or_update_knowledge_agent(self):
        """Create or update the Knowledge Agent in Azure AI Search"""
        if not self.agentic_enabled:
            return
            
        try:
            # Extract deployment name from model config
            chat_deployment = settings.openai_chat_deployment
            
            logger.info(f"Creating/updating knowledge agent '{self.agent_name}' with:")
            logger.info(f"  - OpenAI endpoint: {settings.openai_endpoint}")
            logger.info(f"  - Chat deployment: {chat_deployment}")
            logger.info(f"  - Target index: {settings.search_index}")
            
            agent = KnowledgeAgent(
                name=self.agent_name,
                models=[
                    KnowledgeAgentAzureOpenAIModel(
                        azure_open_ai_parameters=AzureOpenAIVectorizerParameters(
                            resource_url=settings.openai_endpoint,
                            deployment_name=chat_deployment,
                            model_name="gpt-4o-mini",
                            api_key=settings.openai_key
                        )
                    )
                ],
                target_indexes=[
                    KnowledgeAgentTargetIndex(
                        index_name=settings.search_index
                    )
                ],
                request_limits=KnowledgeAgentRequestLimits(
                    max_tokens=4000,
                    max_requests_per_minute=100
                )
            )
            
            if self.index_client:
                await self.index_client.create_or_update_knowledge_agent(agent)
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
        Process a question using agentic retrieval or fallback to basic search
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
            if self.knowledge_agent_client and self.agentic_enabled:
                result = await self._perform_agentic_retrieval(question, conversation_history, tracking_id)
            else:
                result = await self._fallback_process_question(question, tracking_id)
            
            processing_time = time.time() - start_time
            result["processing_time_ms"] = round(processing_time * 1000, 2)
            result["session_id"] = session_id
            result["rag_mode"] = rag_mode
            
            return result
            
        except Exception as e:
            logger.error(f"Error processing question: {e}")
            token_tracker.record_token_usage(
                record_id=tracking_id,
                prompt_tokens=0,
                completion_tokens=0,
                success=False,
                error_message=str(e)
            )
            
            return {
                "answer": f"I apologize, but I encountered an error while processing your question: {str(e)}",
                "citations": [],
                "query_rewrites": [],
                "token_usage": {"total_tokens": 0, "error": str(e)},
                "processing_time_ms": round((time.time() - start_time) * 1000, 2),
                "session_id": session_id,
                "rag_mode": rag_mode,
                "success": False
            }

    async def _perform_agentic_retrieval(self, 
                                       question: str, 
                                       conversation_history: Optional[List[Dict[str, str]]] = None,
                                       tracking_id: Optional[str] = None) -> Dict[str, Any]:
        """Perform agentic retrieval using Azure AI Search Knowledge Agent"""
        try:
            messages = self._build_conversation_messages(question, conversation_history)
            
            request = KnowledgeAgentRetrievalRequest(
                messages=messages,
                index_params=KnowledgeAgentIndexParams(
                    index_name=settings.search_index
                )
            )
            
            # Perform agentic retrieval
            if not self.knowledge_agent_client:
                raise Exception("Knowledge agent client not available")
            response = await self.knowledge_agent_client.retrieve(request)
            
            answer = self._extract_answer_from_response(response)
            citations = self._format_citations_from_references(response.references if hasattr(response, 'references') else [])
            query_rewrites = self._extract_query_rewrites_from_response(response)
            
            token_usage = self._extract_token_usage_from_response(response)
            
            if tracking_id and token_usage:
                token_tracker.record_token_usage(
                    record_id=tracking_id,
                    prompt_tokens=token_usage.get("prompt_tokens", 0),
                    completion_tokens=token_usage.get("completion_tokens", 0),
                    success=True
                )
            
            return {
                "answer": answer,
                "citations": citations,
                "query_rewrites": query_rewrites,
                "token_usage": token_usage,
                "success": True,
                "retrieval_method": "agentic"
            }
            
        except Exception as e:
            logger.error(f"Agentic retrieval failed: {e}")
            raise

    def _build_conversation_messages(self, 
                                   question: str, 
                                   conversation_history: Optional[List[Dict[str, str]]] = None) -> List[Any]:
        """Build conversation messages for the knowledge agent"""
        if not AGENTIC_IMPORTS_AVAILABLE:
            messages = []
            if conversation_history:
                for msg in conversation_history[-5:]:
                    role = msg.get("role", "user")
                    content = msg.get("content", "")
                    if content:
                        messages.append({"role": role, "content": content})
            messages.append({"role": "user", "content": question})
            return messages
        
        messages = []
        
        if conversation_history:
            for msg in conversation_history[-5:]:  # Limit to last 5 messages
                role = msg.get("role", "user")
                content = msg.get("content", "")
                if content:
                    messages.append(
                        KnowledgeAgentMessage(
                            role=role,
                            content=[KnowledgeAgentMessageTextContent(text=content)]
                        )
                    )
        
        messages.append(
            KnowledgeAgentMessage(
                role="user",
                content=[KnowledgeAgentMessageTextContent(text=question)]
            )
        )
        
        return messages

    def _format_citations_from_references(self, references: List[Any]) -> List[Dict[str, Any]]:
        """Format citations from agentic retrieval references"""
        citations = []
        
        for i, ref in enumerate(references):
            try:
                citation = {
                    "id": str(i + 1),
                    "title": getattr(ref, 'title', f'Document {i + 1}'),
                    "content": getattr(ref, 'content', ''),
                    "source": getattr(ref, 'source', ''),
                    "url": getattr(ref, 'url', ''),
                    "score": getattr(ref, 'score', 0.0),
                    "chunk_id": getattr(ref, 'chunk_id', ''),
                }
                citations.append(citation)
            except Exception as e:
                logger.warning(f"Error formatting citation {i}: {e}")
                continue
        
        return citations

    def _extract_query_rewrites_from_response(self, response: Any) -> List[str]:
        """Extract query rewrites from agentic response"""
        query_rewrites = []
        
        try:
            if hasattr(response, 'query_rewrites'):
                query_rewrites = response.query_rewrites
            elif hasattr(response, 'metadata') and response.metadata:
                metadata = response.metadata
                if isinstance(metadata, dict) and 'query_rewrites' in metadata:
                    query_rewrites = metadata['query_rewrites']
        except Exception as e:
            logger.warning(f"Could not extract query rewrites: {e}")
        
        return query_rewrites if isinstance(query_rewrites, list) else []

    def _extract_answer_from_response(self, response: Any) -> str:
        """Extract answer from agentic retrieval response"""
        try:
            if hasattr(response, 'answer'):
                return response.answer
            elif hasattr(response, 'content'):
                return response.content
            elif hasattr(response, 'text'):
                return response.text
            else:
                return "I found relevant information but couldn't generate a complete answer."
        except Exception as e:
            logger.error(f"Error extracting answer: {e}")
            return "I encountered an error while processing the response."

    def _extract_token_usage_from_response(self, response: Any) -> Dict[str, int]:
        """Extract token usage from agentic response"""
        try:
            if hasattr(response, 'usage'):
                usage = response.usage
                if hasattr(usage, 'prompt_tokens'):
                    return {
                        "prompt_tokens": getattr(usage, 'prompt_tokens', 0),
                        "completion_tokens": getattr(usage, 'completion_tokens', 0),
                        "total_tokens": getattr(usage, 'total_tokens', 0)
                    }
            
            if hasattr(response, 'token_usage'):
                usage = response.token_usage
                return {
                    "prompt_tokens": usage.get('prompt_tokens', 0),
                    "completion_tokens": usage.get('completion_tokens', 0),
                    "total_tokens": usage.get('total_tokens', 0)
                }
                
            if hasattr(response, 'prompt_tokens'):
                return {
                    "prompt_tokens": getattr(response, 'prompt_tokens', 0),
                    "completion_tokens": getattr(response, 'completion_tokens', 0),
                    "total_tokens": getattr(response, 'total_tokens', 0)
                }
                
        except Exception as e:
            logger.warning(f"Could not extract token usage: {e}")
        
        return {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

    async def _fallback_process_question(self, question: str, tracking_id: Optional[str] = None) -> Dict[str, Any]:
        """Fallback processing using basic Azure Search when agentic retrieval is not available"""
        try:
            if not self.search_client:
                raise Exception("Search client not available")
            results = self.search_client.search(
                search_text=question,
                top=10,
                include_total_count=True,
                query_type=QueryType.SEMANTIC,
                semantic_configuration_name="multimodal-rag-1750033945665-semantic-configuration",
                query_caption="extractive|highlight-false"
            )
            
            citations = []
            for i, result in enumerate(results):
                citation = {
                    "id": str(i + 1),
                    "title": result.get("document_title", f"Document {i + 1}"),
                    "content": result.get("content_text", ""),
                    "source": result.get("content_path", ""),
                    "score": result.get("@search.score", 0.0),
                    "reranker_score": result.get("@search.reranker_score", 0.0),
                }
                citations.append(citation)
            
            top_content = []
            for citation in citations[:3]:  # Use top 3 results
                if citation["content"]:
                    top_content.append(citation["content"][:500])  # Limit content length
            
            if top_content:
                answer = f"Based on the search results, here's what I found:\n\n" + "\n\n".join(top_content)
            else:
                answer = "I couldn't find specific information to answer your question in the available documents."
            
            if tracking_id:
                estimated_tokens = len(question.split()) + len(answer.split())
                token_tracker.record_token_usage(
                    record_id=tracking_id,
                    prompt_tokens=len(question.split()),
                    completion_tokens=len(answer.split()),
                    success=True
                )
            
            return {
                "answer": answer,
                "citations": citations,
                "query_rewrites": [question],  # No rewrites in fallback mode
                "token_usage": {
                    "prompt_tokens": len(question.split()),
                    "completion_tokens": len(answer.split()),
                    "total_tokens": len(question.split()) + len(answer.split())
                },
                "success": True,
                "retrieval_method": "basic_search"
            }
            
        except Exception as e:
            logger.error(f"Fallback processing failed: {e}")
            raise

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

# Global instance
agentic_rag_service = AgenticVectorRAGService()
