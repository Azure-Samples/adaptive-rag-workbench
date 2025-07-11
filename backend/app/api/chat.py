from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
import json
import asyncio
import uuid
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
from ..services.token_usage_tracker import token_tracker
from ..services.azure_services import get_azure_service_manager

router = APIRouter()

class ChatRequest(BaseModel):
    prompt: str
    mode: str = "fast-rag"  # fast-rag, agentic-rag, deep-research-rag
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
        session_id = request.session_id or str(uuid.uuid4())
        
        if request.mode in ["agentic-rag", "fast-rag", "deep-research-rag"]:
            return await handle_rag_modes(request, session_id, current_user)
        else:
            return await handle_legacy_modes(request, current_user)
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

async def handle_rag_modes(request: ChatRequest, session_id: str, current_user: dict):
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
                "mode": request.mode
            }
            await azure_service_manager.save_session_history(session_id, user_message)
            
            yield f"data: {json.dumps({'type': 'metadata', 'session_id': session_id, 'mode': request.mode, 'timestamp': datetime.utcnow().isoformat()})}\n\n"
            
            if request.mode == "agentic-rag":
                result = await agentic_rag_service.process_question(
                    question=request.prompt,
                    conversation_history=request.conversation_history,
                    rag_mode=request.mode,
                    session_id=session_id
                )
            elif request.mode == "fast-rag":
                result = await process_fast_rag(request.prompt, session_id)
            elif request.mode == "deep-research-rag":
                result = await process_deep_research_rag(request.prompt, session_id, request.verification_level)
            else:
                raise ValueError(f"Unsupported RAG mode: {request.mode}")
            
            answer = result.get("answer", "")
            
            # For agentic responses, send the complete answer at once to preserve markdown formatting
            if request.mode == "agentic-rag":
                yield f"data: {json.dumps({'type': 'answer_complete', 'answer': answer})}\n\n"
            else:
                # For other modes, stream word by word
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
                "token_usage": token_usage,
                "processing_metadata": processing_metadata
            }
            await azure_service_manager.save_session_history(session_id, assistant_message)
            
            yield f"data: {json.dumps({'type': 'done', 'session_id': session_id})}\n\n"
            
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

async def process_fast_rag(prompt: str, session_id: str) -> Dict[str, Any]:
    """
    Process Fast RAG mode using hybrid vector search with Azure AI Search.
    
    This implements the standard RAG pattern with:
    - Hybrid search (text + vector) for enhanced retrieval
    - Semantic ranking for improved relevance
    - Proper citation tracking with source attribution
    - Score-based filtering for quality control
    """
    try:
        import time
        start_time = time.time()
        
        # Perform hybrid search with the enhanced retriever
        docs = await retriever.invoke(
            query=prompt,
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
        
        # Build comprehensive answer with context
        answer_parts = []
        citations = []
        
        # Group documents by company/source for better organization
        doc_groups = {}
        for doc in docs:
            company = doc.get('company', 'Unknown')
            if company not in doc_groups:
                doc_groups[company] = []
            doc_groups[company].append(doc)
        
        # Generate structured response
        answer_parts.append(f"Based on my analysis of {len(docs)} relevant documents, here's what I found:")
        answer_parts.append("")
        
        citation_id = 1
        for company, company_docs in doc_groups.items():
            if company != 'Unknown':
                answer_parts.append(f"**{company}:**")
            
            for doc in company_docs:
                content = doc.get('content', '')
                title = doc.get('title', f'Document {citation_id}')
                
                # Use highlights if available, otherwise use content preview
                highlights = doc.get('highlights', [])
                if highlights:
                    relevant_text = highlights[0][:300]
                else:
                    relevant_text = content[:300]
                
                if relevant_text:
                    answer_parts.append(f"• {relevant_text}...")
                    
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
            
            answer_parts.append("")
        
        # Add methodology note
        answer_parts.append("---")
        answer_parts.append("*This response uses hybrid vector search combining text and semantic search for enhanced relevance.*")
        
        # Calculate search quality metrics
        avg_score = sum(doc.get('search_score', 0) for doc in docs) / len(docs)
        has_reranker_scores = any(doc.get('reranker_score') for doc in docs)
        
        return {
            "answer": "\n".join(answer_parts),
            "citations": citations,
            "query_rewrites": [prompt],  # Fast mode doesn't do query rewriting
            "token_usage": {
                "prompt_tokens": 0,  # Fast RAG doesn't use LLM for generation
                "completion_tokens": 0,
                "total_tokens": 0
            },
            "processing_time_ms": processing_time_ms,
            "retrieval_method": "hybrid_vector_search",
            "documents_retrieved": len(docs),
            "average_relevance_score": round(avg_score, 3),
            "semantic_ranking_used": has_reranker_scores,
            "success": True
        }
        
    except Exception as e:
        import traceback
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
    """Get chat session history"""
    try:
        azure_service_manager = await get_azure_service_manager()
        history = await azure_service_manager.get_session_history(session_id)
        return {"session_id": session_id, "messages": history}
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
async def list_user_sessions(current_user: dict = Depends(get_current_user)):
    """List all sessions for the current user (placeholder implementation)"""
    try:
        return {"sessions": [], "message": "Session listing not yet implemented"}
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
