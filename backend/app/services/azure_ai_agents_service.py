"""
Azure AI Agents Service for Deep Research
Based on the Azure AI Agents sample for deep research functionality
"""

import asyncio
import logging
import os
import time
from typing import Dict, Any, Optional, List
from azure.ai.projects.aio import AIProjectClient
from azure.identity.aio import DefaultAzureCredential
from azure.ai.agents.models import DeepResearchTool, MessageRole, ThreadMessage
from app.core.config import settings
from app.services.token_usage_tracker import token_tracker, ServiceType, OperationType

logger = logging.getLogger(__name__)

class AzureAIAgentsService:
    """Azure AI Agents service for deep research functionality"""
    
    def __init__(self):
        self.project_client = None
        self.agents_client = None
        
    async def initialize(self):
        """Initialize the Azure AI Agents service"""
        try:
            from .azure_ai_project_service import azure_ai_project_service
            await azure_ai_project_service.initialize()
            
            self.project_client = azure_ai_project_service.get_project_client()
            
            # Check if project client was successfully initialized
            if self.project_client is not None:
                self.agents_client = self.project_client.agents
                logger.info("Azure AI Agents service initialized successfully")
            else:
                logger.warning("Azure AI Project client not available, Azure AI Agents service will use fallback mode")
                self.agents_client = None
                
        except Exception as e:
            logger.error(f"Failed to initialize Azure AI Agents service: {e}")
            logger.info("Azure AI Agents service will operate in fallback mode")
            self.project_client = None
            self.agents_client = None
    
    async def process_deep_research(self, 
                                  question: str, 
                                  session_id: str,
                                  tracking_id: Optional[str] = None) -> Dict[str, Any]:
        """Process deep research using Azure AI Agents with o3-deep-research model"""
        try:
            logger.info(f"Processing deep research question: {question}")
            
            # Check if agents client is available
            if self.agents_client is None:
                logger.warning("Azure AI Agents client not available, using fallback research method")
                return await self._fallback_deep_research(question, session_id, tracking_id)
            
            # Get Bing connection ID for Deep Research Tool
            bing_resource_name = os.environ.get("O3_BING_RESOURCE_NAME", "groundingbingsearch")
            conn_id = None
            
            try:
                if self.project_client:
                    connection = await self.project_client.connections.get(name=bing_resource_name)
                    conn_id = connection.id
                    logger.info(f"Retrieved Bing connection ID: {conn_id}")
            except Exception as e:
                logger.warning(f"Could not retrieve Bing connection: {e}")
                return await self._fallback_deep_research(question, session_id, tracking_id)
            
            # Initialize Deep Research tool with environment variables
            deep_research_model = os.environ.get("DEEP_RESEARCH_MODEL_DEPLOYMENT_NAME", "o3-deep-research")
            deep_research_tool = DeepResearchTool(
                bing_grounding_connection_id=conn_id,
                deep_research_model=deep_research_model,
            )
            
            # Create agent with Deep Research tool
            model_deployment = os.environ.get("O3_MODEL_DEPLOYMENT_NAME", "gpt-4o")
            agent = await self.agents_client.create_agent(
                model=model_deployment,
                name="Deep Research Agent",
                instructions="You are a helpful Agent that assists in researching topics comprehensively. Provide detailed, well-sourced answers with proper citations.",
                tools=deep_research_tool.definitions,
            )
            
            logger.info(f"Created deep research agent with ID: {agent.id}")
            
            # Create thread for communication
            thread = await self.agents_client.create_thread()
            logger.info(f"Created thread with ID: {thread.id}")
            
            # Create message to thread
            message = await self.agents_client.create_message(
                thread_id=thread.id,
                role="user",
                content=question
            )
            logger.info(f"Created message with ID: {message.id}")
            
            logger.info("Starting deep research processing... this may take a few minutes")
            
            # Create and poll the run
            run = await self.agents_client.create_run(
                thread_id=thread.id,
                assistant_id=agent.id
            )
            
            last_message_id = None
            while run.status in ("queued", "in_progress"):
                await asyncio.sleep(2)  # Poll every 2 seconds
                run = await self.agents_client.get_run(
                    thread_id=thread.id,
                    run_id=run.id
                )
                
                # Check for new agent responses during processing
                try:
                    response = await self.agents_client.get_last_message_by_role(
                        thread_id=thread.id,
                        role=MessageRole.AGENT,
                    )
                    if response and response.id != last_message_id:
                        logger.info("Received intermediate response from deep research agent")
                        last_message_id = response.id
                except Exception as e:
                    logger.debug(f"No intermediate response available: {e}")
                
                logger.debug(f"Run status: {run.status}")
            
            logger.info(f"Deep research completed with status: {run.status}")
            
            if run.status == "failed":
                error_msg = f"Deep research run failed: {getattr(run, 'last_error', 'Unknown error')}"
                logger.error(error_msg)
                return {
                    "answer": error_msg,
                    "citations": [],
                    "query_rewrites": [question],
                    "token_usage": {"total_tokens": 0, "error": error_msg},
                    "success": False
                }
            
            # Fetch the final message from the agent
            final_message = await self.agents_client.get_last_message_by_role(
                thread_id=thread.id, 
                role=MessageRole.AGENT
            )
            
            if not final_message:
                logger.warning("No final message received from deep research agent")
                return {
                    "answer": "No response generated from deep research agent",
                    "citations": [],
                    "query_rewrites": [question],
                    "token_usage": {"total_tokens": 0},
                    "success": False
                }
            
            # Extract answer from text messages
            answer_parts = []
            if hasattr(final_message, 'text_messages') and final_message.text_messages:
                answer_parts = [t.text.value for t in final_message.text_messages]
            elif hasattr(final_message, 'content') and final_message.content:
                # Fallback for different message structure
                for content_item in final_message.content:
                    if hasattr(content_item, 'text') and hasattr(content_item.text, 'value'):
                        answer_parts.append(content_item.text.value)
            
            answer = "\n\n".join(answer_parts) if answer_parts else "No response content available"
            
            # Extract URL citations
            citations = []
            if hasattr(final_message, 'url_citation_annotations') and final_message.url_citation_annotations:
                seen_urls = set()
                for ann in final_message.url_citation_annotations:
                    url = ann.url_citation.url
                    title = ann.url_citation.title or url
                    if url not in seen_urls:
                        citations.append({
                            "title": title,
                            "url": url,
                            "source": "deep_research"
                        })
                        seen_urls.add(url)
            
            # Extract token usage
            token_usage = self._extract_token_usage_from_run(run)
            
            if tracking_id:
                token_tracker.record_token_usage(
                    record_id=tracking_id,
                    prompt_tokens=token_usage.get("prompt_tokens", 0),
                    completion_tokens=token_usage.get("completion_tokens", 0),
                    success=True
                )
            
            # Clean up: delete the agent
            try:
                await self.agents_client.delete_agent(agent.id)
                logger.info("Deleted deep research agent")
            except Exception as e:
                logger.warning(f"Could not delete agent: {e}")
            
            return {
                "answer": answer,
                "citations": citations,
                "query_rewrites": [question],
                "token_usage": token_usage,
                "tracing_info": {
                    "thread_id": thread.id,
                    "run_id": run.id,
                    "agent_id": agent.id,
                    "status": run.status,
                    "model": deep_research_model,
                    "bing_connection_id": conn_id,
                    "created_at": run.created_at.isoformat() if hasattr(run.created_at, 'isoformat') else str(run.created_at),
                    "completed_at": run.completed_at.isoformat() if hasattr(run.completed_at, 'isoformat') else str(run.completed_at) if run.completed_at else None
                },
                "success": True,
                "retrieval_method": "azure_ai_agents_o3_deep_research"
            }
            
        except Exception as e:
            logger.error(f"Deep research processing failed: {e}")
            if tracking_id:
                token_tracker.record_token_usage(
                    record_id=tracking_id,
                    prompt_tokens=0,
                    completion_tokens=0,
                    success=False,
                    error_message=str(e)
                )
            return {
                "answer": f"Error in Deep Research processing: {str(e)}",
                "citations": [],
                "query_rewrites": [],
                "token_usage": {"total_tokens": 0, "error": str(e)},
                "success": False
            }
    
    async def _fallback_deep_research(self, 
                                    question: str, 
                                    session_id: str,
                                    tracking_id: Optional[str] = None) -> Dict[str, Any]:
        """Fallback deep research method when Azure AI Agents is not available"""
        try:
            logger.info("Using fallback deep research method with enhanced RAG")
            
            # Import the agentic RAG service for fallback
            from .agentic_vector_rag_service import agentic_rag_service
            
            # Ensure the service is initialized
            await agentic_rag_service.ensure_initialized()
            
            # Use agentic RAG as fallback with enhanced verification
            result = await agentic_rag_service.process_question(
                question=question,
                conversation_history=[],
                rag_mode="agentic-rag",
                session_id=session_id
            )
            
            # Enhance the answer to indicate fallback mode
            base_answer = result.get("answer", "")
            enhanced_answer = base_answer + "\n\n---\n*Note: This response was generated using enhanced agentic RAG as Azure AI Agents deep research is currently unavailable.*"
            
            return {
                "answer": enhanced_answer,
                "citations": result.get("citations", []),
                "query_rewrites": result.get("query_rewrites", [question]),
                "token_usage": result.get("token_usage", {}),
                "tracing_info": {
                    "fallback_mode": True,
                    "method": "agentic_rag_fallback",
                    "session_id": session_id
                },
                "success": True,
                "retrieval_method": "agentic_rag_fallback"
            }
            
        except Exception as e:
            logger.error(f"Fallback deep research failed: {e}")
            if tracking_id:
                token_tracker.record_token_usage(
                    record_id=tracking_id,
                    prompt_tokens=0,
                    completion_tokens=0,
                    success=False,
                    error_message=str(e)
                )
            return {
                "answer": f"Deep research is currently unavailable. Error: {str(e)}",
                "citations": [],
                "query_rewrites": [question],
                "token_usage": {"total_tokens": 0, "error": str(e)},
                "success": False
            }
    
    def _extract_token_usage_from_run(self, run: Any) -> Dict[str, int]:
        """Extract token usage from agent run"""
        try:
            if hasattr(run, 'usage'):
                usage = run.usage
                return {
                    "prompt_tokens": getattr(usage, 'prompt_tokens', 0),
                    "completion_tokens": getattr(usage, 'completion_tokens', 0),
                    "total_tokens": getattr(usage, 'total_tokens', 0)
                }
        except Exception as e:
            logger.warning(f"Could not extract token usage from run: {e}")
        
        return {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    
    async def generate_follow_up_questions(self, 
                                         original_question: str, 
                                         answer: str,
                                         session_id: str,
                                         tracking_id: Optional[str] = None) -> Dict[str, Any]:
        """Generate follow-up questions based on the original question and answer"""
        try:
            logger.info(f"Generating follow-up questions for session: {session_id}")
            
            # Check if agents client is available
            if self.agents_client is None:
                logger.warning("Azure AI Agents client not available, using fallback for follow-up questions")
                return await self._fallback_follow_up_questions(original_question, answer, session_id, tracking_id)
            
            agent = await self.agents_client.create_agent(
                model="gpt-4o",
                name="Follow-up Question Generator",
                instructions="""You are a follow-up question generator. Given an original question and its answer, 
                generate 3-5 relevant follow-up questions that would help the user explore the topic deeper. 
                The questions should be:
                1. Specific and actionable
                2. Related to the original topic but exploring different angles
                3. Appropriate for financial/business analysis context
                4. Clear and concise
                
                Return only the questions, one per line, without numbering or bullet points."""
            )
            
            thread = await self.agents_client.create_thread()
            
            prompt = f"""Original Question: {original_question}

Answer: {answer}

Based on the above question and answer, generate 3-5 relevant follow-up questions that would help explore this topic further."""
            
            await self.agents_client.create_message(
                thread_id=thread.id,
                role="user",
                content=prompt
            )
            
            run = await self.agents_client.create_run(
                thread_id=thread.id,
                assistant_id=agent.id
            )
            
            completed_run = await self.agents_client.get_run(
                thread_id=thread.id,
                run_id=run.id
            )
            
            messages = await self.agents_client.list_messages(thread_id=thread.id)
            response = messages.data[0].content[0].text.value if messages.data else ""
            
            follow_up_questions = []
            if response:
                lines = response.strip().split('\n')
                for line in lines:
                    line = line.strip()
                    if line and not line.startswith('#') and len(line) > 10:  # Filter out empty lines and headers
                        cleaned_line = line.lstrip('0123456789.-• ')
                        if cleaned_line:
                            follow_up_questions.append(cleaned_line)
            
            follow_up_questions = follow_up_questions[:5]
            
            token_usage = self._extract_token_usage_from_run(completed_run)
            
            if tracking_id:
                token_tracker.record_token_usage(
                    record_id=tracking_id,
                    prompt_tokens=token_usage.get("prompt_tokens", 0),
                    completion_tokens=token_usage.get("completion_tokens", 0),
                    success=True
                )
            
            return {
                "follow_up_questions": follow_up_questions,
                "token_usage": token_usage,
                "tracing_info": {
                    "thread_id": thread.id,
                    "run_id": run.id,
                    "agent_id": agent.id,
                    "status": completed_run.status,
                    "created_at": completed_run.created_at.isoformat() if hasattr(completed_run.created_at, 'isoformat') else str(completed_run.created_at),
                    "completed_at": completed_run.completed_at.isoformat() if hasattr(completed_run.completed_at, 'isoformat') else str(completed_run.completed_at) if completed_run.completed_at else None
                },
                "success": True
            }
            
        except Exception as e:
            logger.error(f"Follow-up question generation failed: {e}")
            if tracking_id:
                token_tracker.record_token_usage(
                    record_id=tracking_id,
                    prompt_tokens=0,
                    completion_tokens=0,
                    success=False,
                    error_message=str(e)
                )
            return {
                "follow_up_questions": [],
                "token_usage": {"total_tokens": 0, "error": str(e)},
                "success": False
            }
    
    async def _fallback_follow_up_questions(self, 
                                          original_question: str, 
                                          answer: str,
                                          session_id: str,
                                          tracking_id: Optional[str] = None) -> Dict[str, Any]:
        """Fallback method for generating follow-up questions when Azure AI Agents is not available"""
        try:
            logger.info("Using fallback method for follow-up questions generation")
            
            # Import Azure service manager to use OpenAI client
            from .azure_services import get_azure_service_manager
            from ..core.config import settings
            
            azure_manager = await get_azure_service_manager()
            openai_client = azure_manager.async_openai_client
            
            system_prompt = """You are a follow-up question generator. Given an original question and its answer, 
            generate 3-5 relevant follow-up questions that would help the user explore the topic deeper. 
            The questions should be:
            1. Specific and actionable
            2. Related to the original topic but exploring different angles
            3. Appropriate for financial/business analysis context
            4. Clear and concise
            
            Return only the questions, one per line, without numbering or bullet points."""
            
            user_prompt = f"""Original Question: {original_question}

Answer: {answer}

Based on the above question and answer, generate 3-5 relevant follow-up questions that would help explore this topic further."""
            
            response = await openai_client.chat.completions.create(
                model=settings.openai_chat_deployment,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.7,
                max_tokens=500
            )
            
            response_text = response.choices[0].message.content
            
            follow_up_questions = []
            if response_text:
                lines = response_text.strip().split('\n')
                for line in lines:
                    line = line.strip()
                    if line and not line.startswith('#') and len(line) > 10:  # Filter out empty lines and headers
                        cleaned_line = line.lstrip('0123456789.-• ')
                        if cleaned_line:
                            follow_up_questions.append(cleaned_line)
            
            follow_up_questions = follow_up_questions[:5]
            
            token_usage = {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens
            }
            
            if tracking_id:
                token_tracker.record_token_usage(
                    record_id=tracking_id,
                    prompt_tokens=token_usage.get("prompt_tokens", 0),
                    completion_tokens=token_usage.get("completion_tokens", 0),
                    success=True
                )
            
            return {
                "follow_up_questions": follow_up_questions,
                "token_usage": token_usage,
                "tracing_info": {
                    "fallback_mode": True,
                    "method": "openai_fallback",
                    "session_id": session_id
                },
                "success": True
            }
            
        except Exception as e:
            logger.error(f"Fallback follow-up question generation failed: {e}")
            if tracking_id:
                token_tracker.record_token_usage(
                    record_id=tracking_id,
                    prompt_tokens=0,
                    completion_tokens=0,
                    success=False,
                    error_message=str(e)
                )
            return {
                "follow_up_questions": [],
                "token_usage": {"total_tokens": 0, "error": str(e)},
                "success": False
            }

# Global instance
azure_ai_agents_service = AzureAIAgentsService()
