from semantic_kernel.kernel import Kernel
from semantic_kernel.agents import ChatCompletionAgent
# from semantic_kernel.agents.orchestration.sequential import SequentialOrchestration  # Not available in semantic_kernel 1.3.0
from semantic_kernel.connectors.ai.open_ai.services.azure_chat_completion import AzureChatCompletion
from semantic_kernel.contents import ChatMessageContent
from typing import List, Dict, AsyncIterator, Optional
import asyncio
from ..core.config import settings
from .registry import AgentRegistry

class OrchestratorAgent:
    def __init__(self, kernel: Kernel, agent_registry: Optional[AgentRegistry] = None):
        self.kernel = kernel
        self.agent_registry = agent_registry
        self.sk_agents = {}
        self.orchestrations = {}
        
        self.retriever = None
        self.writer = None
        self.verifier = None
        self.curator = None
        
        try:
            self.chat_completion_service = AzureChatCompletion(
                deployment_name=settings.openai_chat_deployment,
                endpoint=settings.openai_endpoint.split('/openai/deployments')[0],
                api_key=settings.openai_key,
                api_version="2025-01-01-preview"
            )
        except Exception as e:
            print(f"Warning: Could not initialize SK chat completion service: {e}")
            self.chat_completion_service = None
        
    def set_agents(self, retriever=None, writer=None, verifier=None, curator=None):
        self.retriever = retriever
        self.writer = writer
        self.verifier = verifier
        self.curator = curator
    
    async def initialize_sk_agents(self):
        """Initialize SK ChatCompletionAgents from registry or create directly"""
        if self.agent_registry:
            self.sk_agents["retriever"] = self.agent_registry.get_agent("retriever_agent")
            self.sk_agents["writer"] = self.agent_registry.get_agent("writer_agent")
            self.sk_agents["verifier"] = self.agent_registry.get_agent("verifier_agent")
            self.sk_agents["curator"] = self.agent_registry.get_agent("curator_agent")
            print("Loaded SK agents from registry")
        elif self.chat_completion_service:
            self.sk_agents["retriever"] = ChatCompletionAgent(
                kernel=self.kernel,
                name="RetrieverAgent",
                instructions="""You are a document retrieval specialist for 10-K financial filings. 
                Your role is to search and retrieve relevant documents from the knowledge base 
                based on user queries about financial information, risks, and business operations.
                Always prioritize the most relevant and recent documents. Use the search_documents tool to find information.""",
                service=self.chat_completion_service
            )
            
            self.sk_agents["writer"] = ChatCompletionAgent(
                kernel=self.kernel,
                name="WriterAgent",
                instructions="""You are a financial analyst assistant specializing in 10-K filing analysis.
                Generate comprehensive, well-structured responses based on retrieved documents.
                Always cite sources using superscript numbers and provide a sources section.
                Focus on accuracy, clarity, and professional financial analysis.""",
                service=self.chat_completion_service
            )
            
            self.sk_agents["verifier"] = ChatCompletionAgent(
                kernel=self.kernel,
                name="VerifierAgent",
                instructions="""You are a source credibility and fact verification specialist.
                Assess the credibility, relevance, and trustworthiness of retrieved documents.
                Provide confidence scores and identify potential conflicts or inconsistencies.
                Consider recency, authority, and relevance in your assessments.""",
                service=self.chat_completion_service
            )
            print("Created SK agents directly")
        else:
            print("Warning: No chat completion service available for SK agents")
        
    async def create_plan(self, request: Dict) -> List[str]:
        mode = request.get("mode", "fast-rag")
        
        if mode == "fast-rag":
            return ["RetrieverAgent", "WriterAgent"]
        elif mode == "agentic-rag":
            return ["AgenticVectorRAGAgent", "WriterAgent"]
        elif mode == "deep-research-rag":
            return ["RetrieverAgent", "VerifierAgent", "AgenticVectorRAGAgent", "WriterAgent"]
        
        elif mode == "context-aware-generation":
            return ["RetrieverAgent", "WriterAgent"]
        elif mode == "qa-verification":
            return ["RetrieverAgent", "VerifierAgent", "WriterAgent"]
        elif mode == "adaptive-kb-management":
            return ["CuratorAgent"]
        
        return ["RetrieverAgent", "WriterAgent"]
    
    async def create_sk_orchestration(self, mode: str) -> Optional[object]:
        """Create SK SequentialOrchestration based on mode using registry config or fallback"""
        await self.initialize_sk_agents()
        
        if not self.sk_agents:
            return None
        
        orchestration_config = None
        if self.agent_registry:
            orchestration_config = self.agent_registry.get_orchestration_config(mode.replace("-", "_"))
        
        if mode == "context-aware-generation":
            agent_sequence = [self.sk_agents["retriever"], self.sk_agents["writer"]]
        elif mode == "qa-verification":
            agent_sequence = [self.sk_agents["retriever"], self.sk_agents["verifier"], self.sk_agents["writer"]]
        elif mode == "adaptive-kb-management":
            if self.sk_agents.get("curator"):
                agent_sequence = [self.sk_agents["curator"]]
            else:
                return None
        else:
            agent_sequence = [self.sk_agents["retriever"], self.sk_agents["writer"]]
        
        agent_sequence = [agent for agent in agent_sequence if agent is not None]
        
        if not agent_sequence:
            return None
        
        try:
            # orchestration = SequentialOrchestration(
            #     members=agent_sequence,
            #     name=f"{mode}_orchestration",
            #     description=orchestration_config.get("description", f"Sequential orchestration for {mode} workflow") if orchestration_config else f"Sequential orchestration for {mode} workflow"
            # )
            # 
            # self.orchestrations[mode] = orchestration
            # return orchestration
            print(f"SK orchestration not available in semantic_kernel 1.3.0, using fallback")
            return None
        except Exception as e:
            print(f"Error creating SK orchestration: {e}")
            return None
    
    async def invoke(self, prompt: str) -> str:
        """Required abstract method implementation"""
        plan = await self.create_plan({"mode": "context-aware-generation"})
        result = ""
        async for token in self.run_stream(prompt, plan):
            result += token
        return result
    
    async def invoke_stream(self, prompt: str) -> AsyncIterator[str]:
        """Required abstract method implementation"""
        plan = await self.create_plan({"mode": "context-aware-generation"})
        async for token in self.run_stream(prompt, plan):
            yield token
    
    async def get_response(self, prompt: str) -> str:
        """Required abstract method implementation"""
        return await self.invoke(prompt)
    
    async def run_stream(self, prompt: str, plan: List[str]) -> AsyncIterator[str]:
        try:
            if "CuratorAgent" in plan and self.curator:
                async for token in self.curator.invoke_stream(prompt):
                    yield token
                return
            
            if "VerifierAgent" in plan:
                mode = "qa-verification"
            else:
                mode = "context-aware-generation"
            
            try:
                orchestration = await self.create_sk_orchestration(mode)
                if orchestration:
                    yield f"Starting SK multi-agent orchestration for {mode}...\n"
                    
                    initial_message = ChatMessageContent(role="user", content=prompt)
                    
                    async for response in orchestration.invoke_stream([initial_message]):
                        if hasattr(response, 'content') and response.content:
                            yield response.content
                        elif isinstance(response, str):
                            yield response
                        else:
                            yield str(response)
                    return
            except Exception as sk_error:
                yield f"SK orchestration failed ({str(sk_error)}), falling back to legacy mode...\n"
            
            async for token in self._fallback_orchestration(prompt, plan):
                yield token
                    
        except Exception as e:
            yield f"Error in orchestration: {str(e)}\n"
    
    async def _fallback_orchestration(self, prompt: str, plan: List[str]) -> AsyncIterator[str]:
        """Fallback to original orchestration logic"""
        retrieved_docs = []
        if "RetrieverAgent" in plan and self.retriever:
            retrieved_docs = await self.retriever.invoke(prompt)
            yield "Retrieved documents from 10-K filings...\n"
            await asyncio.sleep(0.5)
        
        verified_docs = retrieved_docs
        if "VerifierAgent" in plan and self.verifier:
            verified_docs = await self.verifier.invoke(retrieved_docs, prompt)
            avg_confidence = sum(doc.get('confidence', 0) for doc in verified_docs) / len(verified_docs) if verified_docs else 0
            yield f"Verified sources with average confidence: {avg_confidence:.2f}\n"
            await asyncio.sleep(0.5)
        
        if "WriterAgent" in plan and self.writer:
            async for token in self.writer.invoke_stream(verified_docs, prompt):
                yield token
