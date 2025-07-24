"""
MCP RAG Service Implementation for Adaptive RAG Workbench
Acts as an MCP client to communicate with the Azure AI Search MCP server.
Provides similar functionality to Fast RAG but uses MCP server for search operations.
"""

import logging
import time
import json
import httpx
import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime

from app.core.config import settings
from app.services.token_usage_tracker import token_tracker, ServiceType, OperationType

logger = logging.getLogger(__name__)

class MCPRAGService:
    """
    MCP RAG Service that communicates with Azure AI Search via MCP server.
    Provides RAG functionality using Model Context Protocol for search operations.
    """
    
    def __init__(self):
        """Initialize MCP RAG service with configuration."""
        self.mcp_server_url = getattr(settings, 'mcp_server_url', 'http://localhost:8006')
        self.mcp_timeout = getattr(settings, 'mcp_timeout', 30)
        self.default_top_k = getattr(settings, 'mcp_default_top_k', 5)
        self.max_content_length = getattr(settings, 'mcp_max_content_length', 2000)
        
        # HTTP client for MCP communication
        self._client = None
        self._initialized = False
        
        logger.info(f"MCP RAG Service initialized with server URL: {self.mcp_server_url}")
    
    async def ensure_initialized(self):
        """Ensure the service is initialized and MCP server is accessible."""
        if self._initialized:
            return
            
        try:
            if not self._client:
                self._client = httpx.AsyncClient(
                    timeout=httpx.Timeout(self.mcp_timeout),
                    limits=httpx.Limits(max_connections=10, max_keepalive_connections=5)
                )
            
            # Test MCP server connectivity
            await self._test_mcp_connection()
            self._initialized = True
            logger.info("MCP RAG Service initialization completed successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize MCP RAG Service: {str(e)}")
            raise

    async def _test_mcp_connection(self):
        """Test connection to HTTP API server."""
        try:
            response = await self._client.get(f"{self.mcp_server_url}/health")
            if response.status_code == 200:
                logger.info("HTTP API server connection test successful")
            else:
                raise Exception(f"HTTP API server returned status {response.status_code}")
        except Exception as e:
            logger.error(f"HTTP API server connection test failed: {str(e)}")
            raise

    async def _call_mcp_tool(self, tool_name: str, **kwargs) -> Optional[str]:
        """
        Call a tool on the MCP server via REST API.
        
        Args:
            tool_name: Name of the tool to call
            **kwargs: Arguments to pass to the tool
            
        Returns:
            Response from the MCP server or None if error
        """
        if not self._client:
            raise Exception("HTTP client not initialized")
        
        try:
            # Map tool names to REST endpoints
            endpoint_mapping = {
                "keyword_search": "/search/keyword",
                "vector_search": "/search/vector", 
                "hybrid_search": "/search/hybrid",
                "get_search_capabilities": "/capabilities"
            }
            
            endpoint = endpoint_mapping.get(tool_name)
            if not endpoint:
                logger.error(f"Unknown tool: {tool_name}")
                return None
            
            logger.debug(f"Calling MCP tool: {tool_name} with args: {kwargs}")
            
            if tool_name == "get_search_capabilities":
                # GET request for capabilities
                response = await self._client.get(f"{self.mcp_server_url}{endpoint}")
                
                if response.status_code == 200:
                    result = response.json()
                    return json.dumps(result, indent=2)
                else:
                    logger.error(f"MCP server returned status {response.status_code}: {response.text}")
                    return None
            else:
                # POST request for search operations
                payload = {
                    "query": kwargs.get("query", ""),
                    "top": kwargs.get("top", 5),
                    "filters": kwargs.get("filters", "")
                }
                
                response = await self._client.post(
                    f"{self.mcp_server_url}{endpoint}",
                    json=payload,
                    headers={"Content-Type": "application/json"}
                )
                
                if response.status_code == 200:
                    result = response.json()
                    return result.get("markdown", "")
                else:
                    logger.error(f"MCP server returned status {response.status_code}: {response.text}")
                    return None
                
        except Exception as e:
            logger.error(f"Error calling MCP tool {tool_name}: {str(e)}")
            return None

    async def _parse_mcp_search_results(self, mcp_response: str) -> List[Dict[str, Any]]:
        """
        Parse MCP server search response into structured document format.
        
        Args:
            mcp_response: Raw response from MCP server
            
        Returns:
            List of parsed document dictionaries
        """
        documents = []
        
        if not mcp_response or "No results found" in mcp_response:
            return documents
        
        try:
            # Parse markdown-formatted response from MCP server
            lines = mcp_response.split('\n')
            current_doc = {}
            in_content = False
            content_lines = []
            
            for line in lines:
                line = line.strip()
                
                # Document header (e.g., "### 1. Document Title")
                if line.startswith('### ') and '. ' in line:
                    # Save previous document if exists
                    if current_doc and content_lines:
                        current_doc['content'] = ' '.join(content_lines).strip()
                        documents.append(current_doc.copy())
                    
                    # Start new document
                    current_doc = {}
                    content_lines = []
                    in_content = False
                    
                    # Extract title
                    title_part = line.split('. ', 1)
                    if len(title_part) > 1:
                        current_doc['title'] = title_part[1]
                
                # Metadata fields
                elif line.startswith('**Company:**'):
                    current_doc['company'] = line.replace('**Company:**', '').strip()
                elif line.startswith('**Relevance Score:**'):
                    score_str = line.replace('**Relevance Score:**', '').strip()
                    try:
                        current_doc['search_score'] = float(score_str)
                    except ValueError:
                        current_doc['search_score'] = 0.0
                
                # Content section starts after metadata
                elif line == '---':
                    in_content = False
                elif not line.startswith('**') and not line.startswith('###') and not line.startswith('#'):
                    if line and not line.startswith('Found ') and not line.startswith('## '):
                        content_lines.append(line)
                        in_content = True
            
            # Don't forget the last document
            if current_doc and content_lines:
                current_doc['content'] = ' '.join(content_lines).strip()
                documents.append(current_doc)
            
            # Add default values for missing fields
            for doc in documents:
                doc.setdefault('title', 'Unknown Document')
                doc.setdefault('company', '')
                doc.setdefault('content', '')
                doc.setdefault('search_score', 0.0)
                doc.setdefault('document_type', '')
                doc.setdefault('filing_date', '')
                doc.setdefault('page_number', None)
                doc.setdefault('section_type', '')
                doc.setdefault('document_url', '')
                doc.setdefault('form_type', '')
                doc.setdefault('ticker', '')
                doc.setdefault('chunk_id', '')
                doc.setdefault('citation_info', '')
                doc.setdefault('source', 'MCP Search')
            
            logger.info(f"Parsed {len(documents)} documents from MCP response")
            return documents
            
        except Exception as e:
            logger.error(f"Error parsing MCP search results: {str(e)}")
            return []

    async def search_documents(self, query: str, search_type: str = "hybrid", 
                             top_k: Optional[int] = None, filters: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Search documents using HTTP API server.
        
        Args:
            query: Search query
            search_type: Type of search (keyword, vector, hybrid)
            top_k: Maximum number of results
            filters: Optional OData filter expression
            
        Returns:
            List of document dictionaries
        """
        await self.ensure_initialized()
        
        top_k = top_k or self.default_top_k
        filters = filters or ""
        
        try:
            logger.info(f"Performing {search_type} search via HTTP API for query: {query}")
            
            # Call HTTP API directly
            payload = {
                "query": query,
                "top": top_k,
                "filters": filters
            }
            
            response = await self._client.post(
                f"{self.mcp_server_url}/search/{search_type}",
                json=payload,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 200:
                result = response.json()
                documents = result.get("results", [])
                
                # Add default values for missing fields
                for doc in documents:
                    doc.setdefault('source', 'HTTP API Search')
                
                logger.info(f"Retrieved {len(documents)} documents via HTTP API search")
                return documents
            else:
                logger.warning(f"HTTP API returned status {response.status_code}: {response.text}")
                return []
            
        except Exception as e:
            logger.error(f"Error in HTTP API document search: {str(e)}")
            return []

    async def process_question(self, question: str, conversation_history: Optional[List[Dict[str, str]]] = None,
                             session_id: Optional[str] = None, search_type: str = "hybrid") -> Dict[str, Any]:
        """
        Process a question using MCP RAG approach.
        Similar to Fast RAG but uses MCP server for search operations.
        
        Args:
            question: User question
            conversation_history: Previous conversation context
            session_id: Session identifier
            search_type: Type of search to perform
            
        Returns:
            Structured response with answer and metadata
        """
        start_time = time.time()
        tracking_id = token_tracker.start_tracking(
            session_id=session_id or "mcp-rag-session",
            service_type=ServiceType.MCP_RAG,
            operation_type=OperationType.SEARCH,
            endpoint="/mcp-rag"
        )
        
        try:
            await self.ensure_initialized()
            
            # Perform search using MCP server
            docs = await self.search_documents(
                query=question,
                search_type=search_type,
                top_k=self.default_top_k
            )
            
            if not docs:
                # Record no token usage for successful search
                token_tracker.record_token_usage(tracking_id, prompt_tokens=0, completion_tokens=0, success=True)
                return {
                    "answer": "No relevant documents found in the knowledge base for your query. Please try rephrasing your question or use more specific terms.",
                    "citations": [],
                    "query_rewrites": [question],
                    "token_usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
                    "processing_time_ms": int((time.time() - start_time) * 1000),
                    "retrieval_method": f"mcp_{search_type}_search",
                    "documents_retrieved": 0,
                    "success": True
                }
            
            # Generate LLM-synthesized answer from retrieved documents
            logger.info(f"Generating LLM-synthesized answer from {len(docs)} documents")
            llm_result = await self._generate_llm_answer(question, docs, conversation_history)
            
            # Build citations from retrieved documents
            citations = []
            citation_id = 1
            for doc in docs:
                content = doc.get('content', '')
                title = doc.get('title', f'Document {citation_id}')
                
                if content:
                    preview = content[:300] + "..." if len(content) > 300 else content
                    
                    # Build comprehensive citation
                    citation = {
                        'id': str(citation_id),
                        'title': title,
                        'content': preview,
                        'source': doc.get('source', 'MCP Search'),
                        'company': doc.get('company', ''),
                        'document_type': doc.get('document_type', ''),
                        'filing_date': doc.get('filing_date', ''),
                        'page_number': doc.get('page_number'),
                        'section_type': doc.get('section_type', ''),
                        'document_url': doc.get('document_url', ''),
                        'search_score': doc.get('search_score', 0.0),
                        'form_type': doc.get('form_type', ''),
                        'ticker': doc.get('ticker', ''),
                        'chunk_id': doc.get('chunk_id', ''),
                        'citation_info': doc.get('citation_info', ''),
                        'retrieval_method': f'mcp_{search_type}_search'
                    }
                    citations.append(citation)
                    citation_id += 1
            
            # Calculate search quality metrics
            avg_score = sum(doc.get('search_score', 0) for doc in docs) / len(docs) if docs else 0
            processing_time_ms = int((time.time() - start_time) * 1000)
            
            # End token tracking with actual usage
            token_tracker.record_token_usage(
                record_id=tracking_id,
                prompt_tokens=llm_result.get("prompt_tokens", 0),
                completion_tokens=llm_result.get("completion_tokens", 0),
                success=True
            )
            
            return {
                "answer": llm_result.get("answer", "Error generating answer"),
                "citations": citations,
                "query_rewrites": [question],  # MCP mode doesn't do query rewriting
                "token_usage": {
                    "prompt_tokens": llm_result.get("prompt_tokens", 0),
                    "completion_tokens": llm_result.get("completion_tokens", 0),
                    "total_tokens": llm_result.get("prompt_tokens", 0) + llm_result.get("completion_tokens", 0)
                },
                "processing_time_ms": processing_time_ms,
                "retrieval_method": f"mcp_{search_type}_search",
                "documents_retrieved": len(docs),
                "average_relevance_score": round(avg_score, 3),
                "mcp_server_used": True,
                "llm_synthesis_used": True,
                "success": True
            }
            
        except Exception as e:
            import traceback
            
            # End token tracking with error
            token_tracker.record_token_usage(
                record_id=tracking_id,
                prompt_tokens=0,
                completion_tokens=0,
                success=False,
                error_message=str(e)
            )
            
            logger.error(f"Error in MCP RAG processing: {str(e)}")
            return {
                "answer": f"Error in MCP RAG processing: {str(e)}",
                "citations": [],
                "query_rewrites": [],
                "token_usage": {"total_tokens": 0, "error": str(e)},
                "processing_time_ms": int((time.time() - start_time) * 1000),
                "retrieval_method": f"mcp_{search_type}_search",
                "documents_retrieved": 0,
                "error_details": traceback.format_exc(),
                "success": False
            }
    
    async def _generate_llm_answer(self, question: str, docs: List[Dict[str, Any]], 
                                 conversation_history: Optional[List[Dict[str, str]]] = None) -> Dict[str, Any]:
        """
        Generate an LLM-synthesized answer from retrieved documents.
        
        Args:
            question: User question
            docs: Retrieved documents from MCP search
            conversation_history: Previous conversation context
            
        Returns:
            Dictionary with answer and token usage information
        """
        try:
            from openai import AsyncAzureOpenAI
            from app.core.config import settings
            
            # Initialize Azure OpenAI client
            openai_client = AsyncAzureOpenAI(
                api_key=settings.openai_key,
                azure_endpoint=settings.openai_endpoint,
                api_version=settings.openai_api_version
            )
            
            # Build context from retrieved documents
            context_parts = []
            for i, doc in enumerate(docs[:5]):  # Use top 5 documents
                company = doc.get('company', 'Unknown Company')
                title = doc.get('title', f'Document {i+1}')
                content = doc.get('content', '')
                doc_type = doc.get('document_type', '')
                filing_date = doc.get('filing_date', '')
                
                # Build document context
                doc_context = f"**Document {i+1}: {title}**\n"
                if company != 'Unknown Company':
                    doc_context += f"Company: {company}\n"
                if doc_type:
                    doc_context += f"Document Type: {doc_type}\n"
                if filing_date:
                    doc_context += f"Filing Date: {filing_date}\n"
                doc_context += f"Content: {content[:1500]}...\n\n"  # Limit content length
                
                context_parts.append(doc_context)
            
            # Build conversation context if provided
            conversation_context = ""
            if conversation_history:
                conversation_context = "Previous conversation context:\n"
                for msg in conversation_history[-3:]:  # Last 3 messages
                    role = msg.get('role', 'user')
                    content = msg.get('content', '')
                    conversation_context += f"{role.title()}: {content[:200]}...\n"
                conversation_context += "\n"
            
            # Build comprehensive prompt
            system_prompt = """You are a senior financial analyst with expertise in analyzing SEC filings and financial documents. 
Your task is to provide comprehensive, analytical responses based on the provided document excerpts. 

Guidelines:
- Provide detailed, analytical insights based on the document content
- Structure your response with clear sections and headings
- Use specific data points and quotes from the documents
- Reference document sources appropriately  
- Focus on factual information and avoid speculation
- Use professional financial analysis language
- If documents contain conflicting information, acknowledge and explain the differences
- Always cite which documents support your statements"""
            
            user_prompt = f"""{conversation_context}Question: {question}

Based on the following financial document excerpts, provide a comprehensive analytical response:

{chr(10).join(context_parts)}

Please provide a detailed analysis that addresses the question using the information from these documents. Structure your response clearly and cite specific information from the documents."""
            
            # Generate LLM response
            logger.info("Calling Azure OpenAI for answer synthesis...")
            response = await openai_client.chat.completions.create(
                model=settings.openai_chat_deployment,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.1,  # Low temperature for factual responses
                max_tokens=1500,
                top_p=0.9
            )
            
            # Extract response and token usage
            answer = response.choices[0].message.content
            usage = response.usage
            
            # Add methodology note
            answer += f"\n\n---\n*This response was generated using MCP (Model Context Protocol) search with LLM synthesis, analyzing {len(docs)} relevant documents.*"
            
            logger.info(f"LLM synthesis completed. Tokens used: {usage.total_tokens}")
            
            return {
                "answer": answer,
                "prompt_tokens": usage.prompt_tokens,
                "completion_tokens": usage.completion_tokens,
                "total_tokens": usage.total_tokens
            }
            
        except Exception as e:
            logger.error(f"Error generating LLM answer: {str(e)}")
            # Fallback to structured response without LLM
            return await self._generate_fallback_answer(question, docs)
    
    async def _generate_fallback_answer(self, question: str, docs: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Generate a fallback structured answer when LLM synthesis fails.
        
        Args:
            question: User question
            docs: Retrieved documents
            
        Returns:
            Dictionary with fallback answer and zero token usage
        """
        try:
            # Build structured response similar to Fast RAG
            answer_parts = []
            
            # Group documents by company for better organization
            doc_groups = {}
            for doc in docs:
                company = doc.get('company', 'Unknown')
                if company not in doc_groups:
                    doc_groups[company] = []
                doc_groups[company].append(doc)
            
            # Generate structured response
            answer_parts.append(f"Based on analysis of {len(docs)} relevant documents via MCP search:")
            answer_parts.append("")
            
            for company, company_docs in doc_groups.items():
                if company != 'Unknown':
                    answer_parts.append(f"**{company}:**")
                
                for doc in company_docs:
                    content = doc.get('content', '')
                    if content:
                        preview = content[:300] + "..." if len(content) > 300 else content
                        answer_parts.append(f"• {preview}")
                
                answer_parts.append("")
            
            # Add note about fallback mode
            answer_parts.append("---")
            answer_parts.append("*Note: This response uses structured document excerpts due to LLM synthesis unavailability.*")
            
            return {
                "answer": "\n".join(answer_parts),
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0
            }
            
        except Exception as e:
            logger.error(f"Error generating fallback answer: {str(e)}")
            return {
                "answer": f"Error processing documents: {str(e)}",
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0
            }
    
    async def get_mcp_server_status(self) -> Dict[str, Any]:
        """
        Get status information from the HTTP API server.
        
        Returns:
            Status information dictionary
        """
        try:
            await self.ensure_initialized()
            
            capabilities_response = await self._client.get(f"{self.mcp_server_url}/capabilities")
            health_response = await self._client.get(f"{self.mcp_server_url}/health")
            
            if capabilities_response.status_code == 200 and health_response.status_code == 200:
                capabilities = capabilities_response.json()
                health = health_response.json()
                
                return {
                    "status": "connected",
                    "server_url": self.mcp_server_url,
                    "health": health,
                    "capabilities": capabilities,
                    "last_checked": datetime.utcnow().isoformat()
                }
            else:
                return {
                    "status": "error",
                    "server_url": self.mcp_server_url,
                    "error": f"HTTP API server returned error status",
                    "last_checked": datetime.utcnow().isoformat()
                }
            
        except Exception as e:
            return {
                "status": "error",
                "server_url": self.mcp_server_url,
                "error": str(e),
                "last_checked": datetime.utcnow().isoformat()
            }
    
    async def cleanup(self):
        """Clean up resources."""
        if self._client:
            await self._client.aclose()
            self._client = None
        self._initialized = False
        logger.info("MCP RAG Service cleanup completed")

# Global service instance
mcp_rag_service = MCPRAGService()
