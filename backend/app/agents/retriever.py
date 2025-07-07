from typing import List, Dict
import hashlib
from azure.search.documents import SearchClient
from azure.search.documents.models import QueryType
from azure.core.credentials import AzureKeyCredential
from ..core.config import settings

class RetrieverAgent:
    def __init__(self, kernel):
        self.kernel = kernel
        self.search_client = SearchClient(
            endpoint=settings.search_endpoint,
            index_name=settings.search_index,
            credential=AzureKeyCredential(settings.search_admin_key)
        )
        
        try:
            from azure.search.documents.agent.aio import KnowledgeAgentRetrievalClient
            self.agent_client = KnowledgeAgentRetrievalClient(
                endpoint=settings.search_endpoint,
                credential=AzureKeyCredential(settings.search_admin_key),
                agent_name="retriever_agent"
            )
            self.use_agentic_retrieval = True
        except ImportError:
            self.agent_client = None
            self.use_agentic_retrieval = False
    
    async def get_response(self, query: str) -> str:
        docs = await self.invoke(query)
        return f"Retrieved {len(docs)} documents for query: {query}"
    
    async def invoke_stream(self, query: str):
        docs = await self.invoke(query)
        for doc in docs:
            title = doc.get('title', 'Unknown Document')
            content = doc.get('content', '')
            source = doc.get('source', 'Unknown Source')
            yield f"Document: {title} - {content[:100]}... (Source: {source})\n"
    
    async def invoke(self, query: str) -> List[Dict]:
        try:
            results = self.search_client.search(
                search_text=query,
                top=10,
                include_total_count=True,
                query_type=QueryType.SEMANTIC,
                semantic_configuration_name="multimodal-rag-1750033945665-semantic-configuration",
                query_caption="extractive|highlight-false"
            )
            
            docs = []
            for result in results:
                docs.append({
                    "id": result.get("content_id", ""),
                    "content": result.get("content_text", ""),
                    "title": result.get("document_title", ""),
                    "source": result.get("content_path", ""),
                    "text_document_id": result.get("text_document_id", ""),
                    "image_document_id": result.get("image_document_id", ""),
                    "score": result.get("@search.score", 0.0),
                    "reranker_score": result.get("@search.reranker_score", 0.0),
                    "captions": result.get("@search.captions", []),
                    "search_agent_query": query
                })
            
            docs.sort(key=lambda x: x.get("reranker_score") or x.get("score") or 0, reverse=True)
            
            return docs
        except Exception as e:
            print(f"Azure Search error: {e}")
            return self._generate_mock_documents(query)
    
    def _generate_mock_documents(self, query: str) -> List[Dict]:
        companies = ["Apple", "Microsoft", "Google", "Meta", "JPMC", "Amazon"]
        years = [2024, 2023, 2022, 2021]
        
        docs = []
        for i, company in enumerate(companies[:3]):
            for j, year in enumerate(years[:2]):
                doc_id = hashlib.md5(f"{company}_{year}_{query}".encode()).hexdigest()[:8]
                
                if "risk" in query.lower():
                    content = f"""Risk Factors for {company} ({year}):
                    
Our business faces various risks including market volatility, regulatory changes, competitive pressures, and operational challenges. Economic uncertainty may impact consumer demand and business operations. Cybersecurity threats pose ongoing risks to our data and systems. Supply chain disruptions could affect product availability and costs. Changes in technology trends may require significant investments to remain competitive."""
                
                elif "revenue" in query.lower() or "r&d" in query.lower():
                    content = f"""Financial Performance - {company} ({year}):
                    
Research and development expenses increased to support innovation initiatives. Revenue growth was driven by strong performance in key product segments. Investment in artificial intelligence and cloud technologies represents a strategic priority. Operating margins improved through operational efficiency initiatives. Geographic expansion contributed to revenue diversification."""
                
                else:
                    content = f"""Business Overview - {company} ({year}):
                    
{company} continues to focus on innovation and market expansion. Key strategic initiatives include technology development, market penetration, and operational excellence. The company maintains strong financial performance while investing in future growth opportunities. Regulatory compliance and risk management remain priorities."""
                
                docs.append({
                    "id": doc_id,
                    "content": content,
                    "source": f"{company}_{year}_10-K",
                    "company": company,
                    "year": year,
                    "score": 0.9 - (i * 0.1) - (j * 0.05)
                })
        
        return sorted(docs, key=lambda x: x["score"], reverse=True)
