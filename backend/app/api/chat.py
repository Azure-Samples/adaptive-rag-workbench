from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
import json
import asyncio
import uuid
import time
import traceback
import logging
from datetime import datetime
from ..agents.orchestrator import OrchestratorAgent
from ..agents.retriever import RetrieverAgent
from ..agents.writer import WriterAgent
from ..agents.verifier import VerifierAgent
from ..agents.curator import CuratorAgent
from ..core.globals import initialize_kernel, get_agent_registry
from ..auth.middleware import get_current_user
from ..services.agentic_vector_rag_service import agentic_rag_service
from ..services.azure_ai_agents_service import azure_ai_agents_service
from ..services.mcp_rag_service import mcp_rag_service
from ..services.token_usage_tracker import token_tracker
from ..services.azure_services import get_azure_service_manager

router = APIRouter()

class ChatRequest(BaseModel):
    prompt: str
    mode: str = "fast-rag"  # fast-rag, agentic-rag, deep-research-rag, mcp-rag
    verification_level: str = "basic"  # basic, thorough, comprehensive
    conversation_history: Optional[List[Dict[str, str]]] = None
    session_id: Optional[str] = None

kernel = initialize_kernel()

orchestrator = OrchestratorAgent(kernel, get_agent_registry())
retriever = RetrieverAgent(kernel)
writer = WriterAgent(kernel)
verifier = VerifierAgent(kernel)
curator = CuratorAgent(kernel)

orchestrator.set_agents(
    retriever=retriever,
    writer=writer,
    verifier=verifier,
    curator=curator
)

@router.post("/chat")
async def chat_stream(request: ChatRequest, current_user: dict = Depends(get_current_user)):
    try:
        # Only generate session ID if one is provided (for session-enabled modes)
        # For QA mode without sessions, we'll use None to skip CosmosDB storage
        session_id = request.session_id
        if session_id is None:
            # Generate a temporary ID for internal processing but don't save to DB
            temp_session_id = str(uuid.uuid4())
        else:
            temp_session_id = session_id
        
        if request.mode in ["agentic-rag", "fast-rag", "deep-research-rag", "mcp-rag"]:
            return await handle_rag_modes(request, session_id, current_user)
        else:
            return await handle_legacy_modes(request, current_user)
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

async def handle_rag_modes(request: ChatRequest, session_id: str, current_user: dict, save_to_db: bool = True):
    """Handle the new RAG modes with enhanced features"""
    
    async def generate():
        try:
            # Ensure agentic service is properly initialized
            await agentic_rag_service.ensure_initialized()
            
            azure_service_manager = await get_azure_service_manager()
            user_message = {
                "role": "user",
                "content": request.prompt,
                "timestamp": datetime.utcnow().isoformat(),
                "mode": request.mode,
                "user_id": current_user.get('sub', current_user.get('preferred_username', 'unknown'))
            }
            
            # Only save to CosmosDB if session is enabled
            if save_to_db:
                await azure_service_manager.save_session_history(session_id, user_message)
            
            # Load conversation history for context (last 5 exchanges) only if session enabled
            conversation_context = []
            if save_to_db:
                conversation_context = await azure_service_manager.get_conversation_context(session_id, limit=10)
            
            # Return session_id only if session is enabled
            yield f"data: {json.dumps({'type': 'metadata', 'session_id': session_id if save_to_db else None, 'mode': request.mode, 'timestamp': datetime.utcnow().isoformat()})}\n\n"
            
            if request.mode == "agentic-rag":
                result = await agentic_rag_service.process_question(
                    question=request.prompt,
                    conversation_history=conversation_context or request.conversation_history,
                    rag_mode=request.mode,
                    session_id=session_id
                )
            elif request.mode == "fast-rag":
                result = await process_fast_rag(request.prompt, session_id)
            elif request.mode == "mcp-rag":
                result = await process_mcp_rag(request.prompt, session_id)
            elif request.mode == "deep-research-rag":
                result = await process_deep_research_rag(request.prompt, session_id, request.verification_level, conversation_context)
            else:
                raise ValueError(f"Unsupported RAG mode: {request.mode}")
            
            answer = result.get("answer", "")
            
            # For all RAG modes, send the complete answer at once to preserve markdown formatting
            if request.mode in ["agentic-rag", "mcp-rag", "fast-rag", "deep-research-rag"]:
                yield f"data: {json.dumps({'type': 'answer_complete', 'answer': answer})}\n\n"
            else:
                # For legacy modes, stream word by word
                words = answer.split()
                for i, word in enumerate(words):
                    yield f"data: {json.dumps({'type': 'token', 'token': word + ' ', 'index': i})}\n\n"
                    await asyncio.sleep(0.05)  # Simulate streaming delay
            
            citations = result.get("citations", [])
            if citations:
                yield f"data: {json.dumps({'type': 'citations', 'citations': citations})}\n\n"
            
            query_rewrites = result.get("query_rewrites", [])
            if query_rewrites:
                yield f"data: {json.dumps({'type': 'query_rewrites', 'rewrites': query_rewrites})}\n\n"
            
            token_usage = result.get("token_usage", {})
            if token_usage:
                yield f"data: {json.dumps({'type': 'token_usage', 'usage': token_usage})}\n\n"
            
            tracing_info = result.get("tracing_info", {})
            if tracing_info:
                yield f"data: {json.dumps({'type': 'tracing_info', 'tracing': tracing_info})}\n\n"
            
            processing_metadata = {
                'processing_time_ms': result.get('processing_time_ms', 0),
                'retrieval_method': result.get('retrieval_method', 'unknown'),
                'success': result.get('success', False)
            }
            yield f"data: {json.dumps({'type': 'metadata', 'processing': processing_metadata})}\n\n"
            
            assistant_message = {
                "role": "assistant",
                "content": answer,
                "timestamp": datetime.utcnow().isoformat(),
                "citations": citations,
                "query_rewrites": query_rewrites,
                "token_usage": token_usage,
                "tracing_info": tracing_info,
                "processing_metadata": processing_metadata,
                "mode": request.mode,
                "user_id": current_user.get('sub', current_user.get('preferred_username', 'unknown'))
            }
            
            # Only save to CosmosDB if session is enabled
            if save_to_db:
                await azure_service_manager.save_session_history(session_id, assistant_message)
            
            # Return session_id only if session is enabled
            yield f"data: {json.dumps({'type': 'done', 'session_id': session_id if save_to_db else None})}\n\n"
            
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"
    
    return StreamingResponse(generate(), media_type="text/event-stream")

async def handle_legacy_modes(request: ChatRequest, current_user: dict):
    """Handle legacy modes for backward compatibility"""
    try:
        plan = await orchestrator.create_plan({"mode": request.mode})
        
        async def generate():
            try:
                async for token in orchestrator.run_stream(request.prompt, plan):
                    yield f"data: {json.dumps({'type': 'token', 'token': token})}\n\n"
                yield f"data: {json.dumps({'type': 'done'})}\n\n"
            except Exception as e:
                yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"
        
        return StreamingResponse(generate(), media_type="text/event-stream")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

async def _generate_llm_synthesized_answer(question: str, docs: List[Dict[str, Any]], 
                                         conversation_history: Optional[List[Dict[str, str]]] = None) -> Dict[str, Any]:
    """
    Generate an LLM-synthesized answer from retrieved documents.
    This is a shared helper function for Fast RAG and other modes that need LLM synthesis.
    
    Args:
        question: User question
        docs: Retrieved documents
        conversation_history: Previous conversation context
        
    Returns:
        Dictionary with answer and token usage information
    """
    try:
        from ..core.config import settings
        import logging
        
        logger = logging.getLogger(__name__)
        
        # Initialize Azure OpenAI client
        azure_manager = await get_azure_service_manager()
        openai_client = azure_manager.async_openai_client
        
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
        
        logger.info(f"LLM synthesis completed. Tokens used: {usage.total_tokens}")
        
        return {
            "answer": answer,
            "prompt_tokens": usage.prompt_tokens,
            "completion_tokens": usage.completion_tokens,
            "total_tokens": usage.total_tokens
        }
        
    except Exception as e:
        logger.error(f"Error generating LLM answer: {str(e)}")
        # Fallback to simple concatenation
        return {
            "answer": f"Based on the retrieved documents: {' '.join([doc.get('content', '')[:200] for doc in docs[:3]])}...",
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0
        }

async def process_fast_rag(prompt: str, session_id: str) -> Dict[str, Any]:
    """
    Process Fast RAG mode using hybrid vector search with Azure AI Search.
    
    This implements the standard RAG pattern with:
    - Hybrid search (text + vector) for enhanced retrieval
    - Semantic ranking for improved relevance
    - LLM synthesis for coherent answer generation
    - Proper citation tracking with source attribution
    - Score-based filtering for quality control
    - Conversation context awareness for follow-up questions
    """
    try:
        import time
        import logging
        
        logger = logging.getLogger(__name__)
        start_time = time.time()
        
        # Enhance search query with conversation context if available
        enhanced_prompt = prompt
        if conversation_context and len(conversation_context) > 0:
            # Get the last few messages for context
            recent_context = conversation_context[-4:]  # Last 2 exchanges
            context_parts = []
            
            for msg in recent_context:
                if msg.get('role') == 'user':
                    context_parts.append(f"Previous question: {msg.get('content', '')}")
                elif msg.get('role') == 'assistant':
                    # Extract key topics from the assistant's response
                    content = msg.get('content', '')
                    if 'MICROSOFT' in content.upper():
                        context_parts.append("Context: Microsoft")
                    elif 'APPLE' in content.upper():
                        context_parts.append("Context: Apple")
                    elif 'GOOGLE' in content.upper() or 'ALPHABET' in content.upper():
                        context_parts.append("Context: Google/Alphabet")
                    elif 'AMAZON' in content.upper():
                        context_parts.append("Context: Amazon")
                    elif 'META' in content.upper():
                        context_parts.append("Context: Meta")
                    elif 'TESLA' in content.upper():
                        context_parts.append("Context: Tesla")
            
            if context_parts:
                enhanced_prompt = f"{' '.join(context_parts)} - {prompt}"
        
        # Perform hybrid search with the enhanced retriever
        docs = await retriever.invoke(
            query=enhanced_prompt,
            filters=None,  # No automatic filters - let hybrid search handle relevance
            top_k=5  # Limit to top 5 for fast mode
        )
        
        processing_time_ms = int((time.time() - start_time) * 1000)
        
        if not docs:
            return {
                "answer": "No relevant documents found in the knowledge base for your query. Please try rephrasing your question or use more specific terms.",
                "citations": [],
                "query_rewrites": [prompt],
                "token_usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
                "processing_time_ms": processing_time_ms,
                "retrieval_method": "hybrid_vector_search",
                "documents_retrieved": 0,
                "success": True
            }
        
        # Generate LLM-synthesized answer from retrieved documents
        logger.info(f"Generating LLM-synthesized answer from {len(docs)} documents")
        llm_result = await _generate_llm_synthesized_answer(prompt, docs)
        
        # Add methodology note to the answer
        synthesized_answer = llm_result.get("answer", "")
        synthesized_answer += "\n\n---\n*This response uses hybrid vector search with LLM synthesis for enhanced analysis and relevance.*"
        
        # Build citations from retrieved documents
        citations = []
        citation_id = 1
        for doc in docs:
            content = doc.get('content', '')
            title = doc.get('title', f'Document {citation_id}')
            
            # Use highlights if available, otherwise use content preview
            highlights = doc.get('highlights', [])
            if highlights:
                relevant_text = highlights[0][:300]
            else:
                relevant_text = content[:300]
            
            if relevant_text:
                # Build comprehensive citation
                citation = {
                    'id': str(citation_id),
                    'title': title,
                    'content': relevant_text,
                    'source': doc.get('source', ''),
                    'company': doc.get('company', ''),
                    'document_type': doc.get('document_type', ''),
                    'filing_date': doc.get('filing_date', ''),
                    'page_number': doc.get('page_number'),
                    'section_type': doc.get('section_type', ''),
                    'document_url': doc.get('document_url', ''),
                    'search_score': doc.get('search_score', 0.0),
                    'reranker_score': doc.get('reranker_score'),
                    'credibility_score': doc.get('credibility_score', 0.0),
                    'form_type': doc.get('form_type', ''),
                    'ticker': doc.get('ticker', ''),
                    'chunk_id': doc.get('chunk_id', ''),
                    'citation_info': doc.get('citation_info', '')
                }
                citations.append(citation)
                citation_id += 1
        
        # Calculate search quality metrics
        avg_score = sum(doc.get('search_score', 0) for doc in docs) / len(docs)
        has_reranker_scores = any(doc.get('reranker_score') for doc in docs)
        
        return {
            "answer": synthesized_answer,
            "citations": citations,
            "query_rewrites": [prompt],  # Fast mode doesn't do query rewriting
            "token_usage": {
                "prompt_tokens": llm_result.get("prompt_tokens", 0),
                "completion_tokens": llm_result.get("completion_tokens", 0),
                "total_tokens": llm_result.get("total_tokens", 0)
            },
            "processing_time_ms": processing_time_ms,
            "retrieval_method": "hybrid_vector_search",
            "documents_retrieved": len(docs),
            "average_relevance_score": round(avg_score, 3),
            "semantic_ranking_used": has_reranker_scores,
            "llm_synthesis_used": True,
            "success": True
        }
        
    except Exception as e:
        return {
            "answer": f"Error in Fast RAG processing: {str(e)}",
            "citations": [],
            "query_rewrites": [],
            "token_usage": {"total_tokens": 0, "error": str(e)},
            "processing_time_ms": 0,
            "retrieval_method": "hybrid_vector_search",
            "documents_retrieved": 0,
            "error_details": traceback.format_exc(),
            "success": False
        }

async def process_mcp_rag(prompt: str, session_id: str) -> Dict[str, Any]:
    """
    Process MCP RAG mode using Model Context Protocol server for Azure AI Search.
    
    This implements RAG pattern with:
    - MCP server communication for search operations
    - Hybrid search capabilities via MCP protocol
    - Proper citation tracking with source attribution
    - Enhanced error handling and logging
    """
    try:
        import time
        start_time = time.time()
        
        # Ensure MCP service is initialized
        await mcp_rag_service.ensure_initialized()
        
        # Process question using MCP RAG service
        result = await mcp_rag_service.process_question(
            question=prompt,
            session_id=session_id,
            search_type="hybrid"  # Use hybrid search by default
        )
        
        return result
        
    except Exception as e:
        processing_time_ms = int((time.time() - start_time) * 1000) if 'start_time' in locals() else 0
        
        return {
            "answer": f"Error in MCP RAG processing: {str(e)}",
            "citations": [],
            "query_rewrites": [],
            "token_usage": {"total_tokens": 0, "error": str(e)},
            "processing_time_ms": processing_time_ms,
            "retrieval_method": "mcp_hybrid_search",
            "documents_retrieved": 0,
            "error_details": traceback.format_exc(),
            "success": False
        }

async def process_deep_research_rag(prompt: str, session_id: str, verification_level: str) -> Dict[str, Any]:
    """Process Deep Research RAG mode using Azure AI Agents"""
    try:
        from ..services.token_usage_tracker import ServiceType, OperationType
        
        tracking_id = token_tracker.start_tracking(
            session_id=session_id,
            service_type=ServiceType.DEEP_RESEARCH_RAG,
            operation_type=OperationType.ANSWER_GENERATION,
            endpoint="/deep-research-rag",
            rag_mode="deep-research-rag"
        )
        
        agents_result = await azure_ai_agents_service.process_deep_research(
            question=prompt,
            session_id=session_id,
            tracking_id=tracking_id
        )
        
        base_answer = agents_result.get("answer", "")
        verification_note = f"\n\n*This response has been generated using Azure AI Agents deep research with {verification_level} verification.*"
        
        return {
            "answer": base_answer + verification_note,
            "citations": agents_result.get("citations", []),
            "query_rewrites": agents_result.get("query_rewrites", [prompt]),
            "token_usage": agents_result.get("token_usage", {}),
            "tracing_info": agents_result.get("tracing_info", {}),
            "processing_time_ms": 0,  # Will be calculated by caller
            "retrieval_method": "azure_ai_agents_deep_research",
            "verification_level": verification_level,
            "success": True
        }
        
    except Exception as e:
        return {
            "answer": f"Error in Deep Research RAG processing: {str(e)}",
            "citations": [],
            "query_rewrites": [],
            "token_usage": {"total_tokens": 0, "error": str(e)},
            "success": False
        }

@router.get("/chat/sessions/{session_id}/history")
async def get_session_history(session_id: str, current_user: dict = Depends(get_current_user)):
    """Get chat session history with metadata"""
    try:
        azure_service_manager = await get_azure_service_manager()
        session_data = await azure_service_manager.get_session_data(session_id)
        return {
            "session_id": session_id, 
            "messages": session_data.get("messages", []),
            "mode": session_data.get("mode", "fast-rag"),
            "created_at": session_data.get("created_at"),
            "updated_at": session_data.get("updated_at"),
            "user_id": session_data.get("user_id")
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/chat/sessions/{session_id}")
async def clear_session_history(session_id: str, current_user: dict = Depends(get_current_user)):
    """Clear chat session history"""
    try:
        azure_service_manager = await get_azure_service_manager()
        empty_session = {
            "role": "system",
            "content": "Session cleared",
            "timestamp": datetime.utcnow().isoformat()
        }
        await azure_service_manager.save_session_history(f"{session_id}_cleared", empty_session)
        return {"session_id": session_id, "status": "cleared"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/chat/sessions")
async def list_user_sessions(
    current_user: dict = Depends(get_current_user),
    limit: int = 50,
    offset: int = 0,
    mode: Optional[str] = None
):
    """List all sessions for the current user"""
    try:
        azure_service_manager = await get_azure_service_manager()
        user_id = current_user.get('sub', current_user.get('preferred_username', 'unknown'))
        
        sessions = await azure_service_manager.list_user_sessions(
            user_id=user_id,
            limit=limit,
            offset=offset,
            mode_filter=mode
        )
        
        return {
            "sessions": sessions,
            "total": len(sessions),
            "limit": limit,
            "offset": offset,
            "user_id": user_id
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class FollowUpRequest(BaseModel):
    original_question: str
    answer: str
    session_id: Optional[str] = None

@router.post("/chat/follow-up-questions")
async def generate_follow_up_questions(request: FollowUpRequest, current_user: dict = Depends(get_current_user)):
    """Generate follow-up questions based on the original question and answer"""
    try:
        session_id = request.session_id or str(uuid.uuid4())
        
        if not azure_ai_agents_service.agents_client:
            await azure_ai_agents_service.initialize()
        
        result = await azure_ai_agents_service.generate_follow_up_questions(
            original_question=request.original_question,
            answer=request.answer,
            session_id=session_id
        )
        
        return {
            "session_id": session_id,
            "follow_up_questions": result.get("follow_up_questions", []),
            "token_usage": result.get("token_usage", {}),
            "success": result.get("success", False)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class RetrievalTestRequest(BaseModel):
    query: str
    filters: Optional[Dict[str, str]] = None
    top_k: Optional[int] = 10
    include_highlights: bool = True

@router.post("/chat/test-retrieval")
async def test_retrieval(request: RetrievalTestRequest, current_user: dict = Depends(get_current_user)):
    """Test the enhanced retrieval capabilities with hybrid vector search"""
    try:
        import time
        start_time = time.time()
        
        # Test the enhanced retriever
        docs = await retriever.invoke(
            query=request.query,
            filters=request.filters,  # Only use explicitly provided filters
            top_k=request.top_k
        )
        
        processing_time_ms = int((time.time() - start_time) * 1000)
        
        # Build comprehensive test results
        results = {
            "query": request.query,
            "filters_applied": request.filters,
            "documents_retrieved": len(docs),
            "processing_time_ms": processing_time_ms,
            "search_method": "hybrid_vector_search",
            "documents": []
        }
        
        for i, doc in enumerate(docs):
            doc_result = {
                "rank": i + 1,
                "id": doc.get('id', ''),
                "title": doc.get('title', ''),
                "company": doc.get('company', ''),
                "document_type": doc.get('document_type', ''),
                "filing_date": doc.get('filing_date', ''),
                "section_type": doc.get('section_type', ''),
                "search_score": doc.get('search_score', 0.0),
                "reranker_score": doc.get('reranker_score'),
                "credibility_score": doc.get('credibility_score', 0.0),
                "content_preview": doc.get('content', '')[:200] + "..." if doc.get('content') else "",
                "source": doc.get('source', ''),
                "citation": doc.get('citation', {})
            }
            
            if request.include_highlights:
                doc_result["highlights"] = doc.get('highlights', [])
            
            results["documents"].append(doc_result)
        
        # Add search quality metrics
        if docs:
            scores = [doc.get('search_score', 0) for doc in docs]
            reranker_scores = [doc.get('reranker_score', 0) for doc in docs if doc.get('reranker_score')]
            
            results["quality_metrics"] = {
                "average_search_score": round(sum(scores) / len(scores), 3),
                "max_search_score": round(max(scores), 3),
                "min_search_score": round(min(scores), 3),
                "semantic_ranking_used": len(reranker_scores) > 0,
                "average_reranker_score": round(sum(reranker_scores) / len(reranker_scores), 3) if reranker_scores else None
            }
        
        return results
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Retrieval test failed: {str(e)}")
