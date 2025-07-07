"""
Azure AI Agents Service for Deep Research
Based on the Azure AI Agents sample for deep research functionality
"""

import asyncio
import logging
import os
from typing import Dict, Any, Optional, List
from azure.ai.projects.aio import AIProjectClient
from azure.identity.aio import DefaultAzureCredential
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
            self.agents_client = self.project_client.agents
            logger.info("Azure AI Agents service initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Azure AI Agents service: {e}")
            raise
    
    async def process_deep_research(self, 
                                  question: str, 
                                  session_id: str,
                                  tracking_id: Optional[str] = None) -> Dict[str, Any]:
        """Process deep research using Azure AI Agents"""
        try:
            logger.info(f"Processing deep research question: {question}")
            
            agent = await self.agents_client.create_agent(
                model="gpt-4",
                name="Deep Research Agent",
                instructions="You are a deep research assistant. Provide comprehensive, well-sourced answers with citations."
            )
            
            thread = await self.agents_client.create_thread()
            
            await self.agents_client.create_message(
                thread_id=thread.id,
                role="user",
                content=question
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
            answer = messages.data[0].content[0].text.value if messages.data else "No response generated"
            
            token_usage = self._extract_token_usage_from_run(completed_run)
            
            if tracking_id:
                token_tracker.record_token_usage(
                    record_id=tracking_id,
                    prompt_tokens=token_usage.get("prompt_tokens", 0),
                    completion_tokens=token_usage.get("completion_tokens", 0),
                    success=True
                )
            
            return {
                "answer": answer,
                "citations": [],  # Extract from agent response
                "query_rewrites": [question],
                "token_usage": token_usage,
                "success": True,
                "retrieval_method": "azure_ai_agents_deep_research"
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
            
            agent = await self.agents_client.create_agent(
                model="gpt-4",
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

# Global instance
azure_ai_agents_service = AzureAIAgentsService()
