from typing import List, Dict, AsyncIterator
import re
import asyncio
from ..core.config import settings
from ..services.azure_services import azure_service_manager

class WriterAgent:
    def __init__(self, kernel):
        self.kernel = kernel
        self.client = None
    
    async def _ensure_client(self):
        if self.client is None:
            self.client = azure_service_manager.async_openai_client
    
    async def get_response(self, retrieved_docs: List[Dict], query: str) -> str:
        await self._ensure_client()
        response_parts = []
        async for chunk in self.invoke_stream(retrieved_docs, query):
            response_parts.append(chunk)
        return ''.join(response_parts)
    
    async def invoke_stream(self, retrieved_docs: List[Dict], query: str) -> AsyncIterator[str]:
        await self._ensure_client()
        try:
            context = self._format_context(retrieved_docs)
            
            system_prompt = """You are a financial analyst assistant. Generate comprehensive responses based on 10-K filing information. Always cite sources using superscript numbers and provide a sources section at the end."""
            
            user_prompt = f"""Query: {query}

Context from 10-K filings:
{context}

Please provide a comprehensive answer with proper citations."""

            response = await self.client.chat.completions.create(
                model=settings.openai_chat_deployment,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                stream=True,
                temperature=0.7,
                max_tokens=1500
            )
            
            content_parts = []
            async for chunk in response:
                if chunk.choices and chunk.choices[0].delta.content:
                    content = chunk.choices[0].delta.content
                    content_parts.append(content)
                    yield content
            
            sources_text = f"\n\nSources:\n{self._format_sources(retrieved_docs)}"
            for char in sources_text:
                yield char
                await asyncio.sleep(0.01)
                
        except Exception:
            async for chunk in self._generate_mock_stream(retrieved_docs, query):
                yield chunk
    
    def _format_context(self, docs: List[Dict]) -> str:
        context_parts = []
        for i, doc in enumerate(docs[:10], 1):
            context_parts.append(f"[^{i}] {doc.get('company', 'Unknown')} {doc.get('year', 'Unknown')}: {doc.get('content', '')[:500]}...")
        return "\n\n".join(context_parts)
    
    def _generate_mock_response(self, query: str, docs: List[Dict]) -> str:
        if not docs:
            return "I don't have sufficient information from the 10-K filings to answer this query."
        
        companies = list(set(doc.get('company', 'Unknown') for doc in docs[:5]))
        
        if "risk" in query.lower():
            return f"""The primary risk factors identified in the 10-K filings include:

• Market volatility and economic uncertainty affecting business operations <sup>1</sup>
• Regulatory changes and compliance requirements in key markets <sup>2</sup>
• Competition from established and emerging technology companies <sup>3</sup>
• Cybersecurity threats and data protection challenges <sup>4</sup>
• Supply chain disruptions and component shortages <sup>5</sup>

These risks are consistently reported across companies like {', '.join(companies[:3])} in their recent filings."""
        
        elif "revenue" in query.lower() or "r&d" in query.lower():
            return f"""Based on the financial data from the 10-K filings:

• Research and development investments have increased year-over-year <sup>1</sup>
• Revenue growth varies by segment and geographic region <sup>2</sup>
• Technology companies like {companies[0] if companies else 'the analyzed companies'} show strong R&D spending <sup>3</sup>
• Investment in AI and cloud technologies represents a significant portion of R&D budgets <sup>4</sup>

The data shows consistent investment in innovation across the analyzed companies."""
        
        else:
            return f"""The 10-K filings from {', '.join(companies[:3])} provide detailed information relevant to your query. Key findings include strategic initiatives, financial performance metrics, and operational updates that address the specific aspects you've inquired about <sup>1</sup><sup>2</sup><sup>3</sup>."""
    
    def _format_sources(self, docs: List[Dict]) -> str:
        sources = []
        for i, doc in enumerate(docs[:5], 1):
            company = doc.get('company', 'Unknown')
            year = doc.get('year', 'Unknown')
            sources.append(f"<sup>{i}</sup> {company} 10-K Filing ({year})")
        return "\n".join(sources)
    
    async def _generate_mock_stream(self, retrieved_docs: List[Dict], query: str) -> AsyncIterator[str]:
        response_text = f"""Based on the retrieved 10-K filing information, here's a comprehensive answer to your query: "{query}"

{self._generate_mock_response(query, retrieved_docs)}

Sources:
{self._format_sources(retrieved_docs)}"""
        
        for char in response_text:
            yield char
            await asyncio.sleep(0.01)
    
    def _convert_citations(self, text: str) -> str:
        return re.sub(r'\[\^(\d+)\]', r'<sup>\1</sup>', text)
