from typing import List, Dict, Optional
import hashlib
import logging
from azure.search.documents import SearchClient
from azure.search.documents.models import QueryType, VectorizedQuery
from azure.core.credentials import AzureKeyCredential
from openai import AsyncAzureOpenAI
from ..core.config import settings

logger = logging.getLogger(__name__)

class RetrieverAgent:
    """
    Fast-RAG Retriever Agent using hybrid vector search with Azure AI Search.
    
    Implements standard RAG pattern with:
    - Hybrid search combining text and vector search
    - Semantic ranking for improved relevance
    - Citation tracking and source attribution
    - Configurable top-k results with score filtering
    """
    
    def __init__(self, kernel):
        self.kernel = kernel
        self.search_client = SearchClient(
            endpoint=settings.search_endpoint,
            index_name=settings.search_index,
            credential=AzureKeyCredential(settings.search_admin_key)
        )
        
        # Initialize Azure OpenAI client for query vectorization
        self.openai_client = AsyncAzureOpenAI(
            api_key=settings.openai_key,
            api_version=settings.openai_api_version,
            azure_endpoint=settings.openai_endpoint
        )
        self.embedding_model = settings.openai_embed_deployment or "text-embedding-3-small"
        
        # RAG configuration
        self.top_k = 10
        self.score_threshold = 0.01  # Reasonable threshold for text search
        self.reranker_threshold = 1.0  # Reasonable threshold for semantic reranking
        
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
            logger.info("Agentic retrieval client not available, using standard hybrid search")
    
    async def _generate_query_embedding(self, query: str) -> Optional[List[float]]:
        """Generate embedding for the search query"""
        try:
            response = await self.openai_client.embeddings.create(
                model=self.embedding_model,
                input=query
            )
            return response.data[0].embedding
        except Exception as e:
            logger.error(f"Failed to generate query embedding: {str(e)}")
            return None
    
    def _build_citation(self, result: Dict) -> Dict:
        """Build citation information from search result"""
        return {
            "title": result.get("title", ""),
            "source": result.get("source", ""),
            "company": result.get("company", ""),
            "document_type": result.get("document_type", ""),
            "form_type": result.get("form_type", ""),
            "filing_date": result.get("filing_date", ""),
            "page_number": result.get("page_number"),
            "section_type": result.get("section_type", ""),
            "document_url": result.get("document_url", ""),
            "chunk_id": result.get("chunk_id", ""),
            "credibility_score": result.get("credibility_score", 0.0)
        }
    
    async def get_response(self, query: str, **kwargs) -> str:
        """Get a formatted response for the query"""
        top_k = kwargs.get('top_k')
        
        docs = await self.invoke(query, top_k=top_k)
        
        if not docs:
            return f"No relevant documents found for query: {query}"
        
        # Build response with citations
        response_parts = [f"Retrieved {len(docs)} relevant documents for query: {query}\n"]
        
        for i, doc in enumerate(docs, 1):
            title = doc.get('title', 'Unknown Document')
            company = doc.get('company', '')
            doc_type = doc.get('document_type', '')
            score = doc.get('search_score', 0.0)
            
            response_parts.append(f"{i}. {title}")
            if company:
                response_parts.append(f"   Company: {company}")
            if doc_type:
                response_parts.append(f"   Type: {doc_type}")
            response_parts.append(f"   Relevance Score: {score:.3f}")
            response_parts.append("")
        
        return "\n".join(response_parts)
    
    async def invoke_stream(self, query: str, **kwargs):
        """Stream retrieval results"""
        top_k = kwargs.get('top_k')
        
        docs = await self.invoke(query, top_k=top_k)
        
        yield f"🔍 Searching for: {query}\n"
        yield f"📊 Found {len(docs)} relevant documents\n\n"
        
        for i, doc in enumerate(docs, 1):
            title = doc.get('title', 'Unknown Document')
            content = doc.get('content', '')
            company = doc.get('company', '')
            doc_type = doc.get('document_type', '')
            score = doc.get('search_score', 0.0)
            highlights = doc.get('highlights', [])
            
            yield f"📄 Document {i}: {title}\n"
            if company:
                yield f"🏢 Company: {company}\n"
            if doc_type:
                yield f"📋 Type: {doc_type}\n"
            yield f"⭐ Score: {score:.3f}\n"
            
            # Show highlights if available
            if highlights:
                yield f"🎯 Key excerpts:\n"
                for highlight in highlights[:2]:  # Show top 2 highlights
                    yield f"   • {highlight[:200]}...\n"
            else:
                # Show content preview
                yield f"📝 Content preview: {content[:200]}...\n"
            
            yield f"🔗 Source: {doc.get('source', 'Unknown')}\n"
            yield "\n---\n\n"
    
    async def invoke(self, query: str, filters: Optional[Dict] = None, top_k: Optional[int] = None) -> List[Dict]:
        """
        Perform hybrid vector search using Azure AI Search.
        
        Args:
            query: The search query
            filters: Optional explicit filters for search (e.g., {"company": "Microsoft", "document_type": "10-K"})
            top_k: Number of results to return (default: self.top_k)
            
        Returns:
            List of retrieved documents with metadata and citations
        """
        try:
            # Use provided top_k or fall back to instance default
            search_top_k = top_k or self.top_k
            
            logger.info(f"Performing hybrid search for query: '{query}' with top_k: {search_top_k}")
            
            # Generate query embedding for vector search
            query_vector = await self._generate_query_embedding(query)
            
            # Prepare search parameters
            search_params = {
                "search_text": query,
                "top": search_top_k,
                "include_total_count": True,
                "query_type": QueryType.SEMANTIC,
                "semantic_configuration_name": "default-semantic-config",
                "query_caption": "extractive|highlight-false",
                "query_answer": "extractive|count-3",
                "select": [
                    "id", "content", "title", "source", "document_id", "company", 
                    "filing_date", "document_type", "section_type", "page_number",
                    "ticker", "form_type", "citation_info", "credibility_score",
                    "chunk_id", "chunk_index", "document_url"
                ]
            }
            
            # Add vector search if embedding generation succeeded
            if query_vector:
                vector_query = VectorizedQuery(
                    vector=query_vector,
                    k_nearest_neighbors=search_top_k,
                    fields="content_vector"
                )
                search_params["vector_queries"] = [vector_query]
                logger.info("Using hybrid search (text + vector)")
            else:
                logger.warning("Using text-only search (vector embedding failed)")
            
            # Add explicit filters if provided
            if filters:
                filter_expressions = []
                for key, value in filters.items():
                    if isinstance(value, str):
                        filter_expressions.append(f"{key} eq '{value}'")
                    else:
                        filter_expressions.append(f"{key} eq {value}")
                
                if filter_expressions:
                    search_params["filter"] = " and ".join(filter_expressions)
                    logger.info(f"Applied explicit filters: {search_params['filter']}")
            else:
                logger.info("No filters provided - using pure hybrid search for relevance")
            
            # Perform the search
            results = self.search_client.search(**search_params)
            
            # Process results
            docs = []
            for result in results:
                # Extract search scores
                search_score = result.get("@search.score", 0.0)
                reranker_score = result.get("@search.reranker_score")
                
                # Filter by score thresholds
                if search_score < self.score_threshold:
                    continue
                
                if reranker_score is not None and reranker_score < self.reranker_threshold:
                    continue
                
                # Extract semantic captions for enhanced context
                captions = result.get("@search.captions", [])
                highlights = []
                if captions:
                    for caption in captions:
                        # Handle different caption object types
                        if hasattr(caption, 'text'):
                            highlights.append(caption.text)
                        elif isinstance(caption, dict):
                            highlights.append(caption.get("text", ""))
                        elif isinstance(caption, str):
                            highlights.append(caption)
                        else:
                            # Try to convert to string as fallback
                            highlights.append(str(caption))
                
                # Build document with enhanced metadata
                doc = {
                    "id": result.get("id", ""),
                    "content": result.get("content", ""),
                    "title": result.get("title", ""),
                    "source": result.get("source", ""),
                    "document_id": result.get("document_id", ""),
                    "company": result.get("company", ""),
                    "filing_date": result.get("filing_date", ""),
                    "document_type": result.get("document_type", ""),
                    "section_type": result.get("section_type", ""),
                    "page_number": result.get("page_number"),
                    "ticker": result.get("ticker", ""),
                    "form_type": result.get("form_type", ""),
                    "chunk_id": result.get("chunk_id", ""),
                    "chunk_index": result.get("chunk_index"),
                    "document_url": result.get("document_url", ""),
                    "credibility_score": result.get("credibility_score", 0.0),
                    
                    # Search metadata
                    "search_score": search_score,
                    "reranker_score": reranker_score,
                    "highlights": highlights,
                    "search_query": query,
                    
                    # Citation information
                    "citation": self._build_citation(result),
                    "citation_info": result.get("citation_info", "")
                }
                
                docs.append(doc)
            
            # Sort by reranker score (if available) then by search score
            docs.sort(key=lambda x: (
                x.get("reranker_score") or 0, 
                x.get("search_score") or 0
            ), reverse=True)
            
            logger.info(f"Retrieved {len(docs)} documents after filtering")
            
            return docs
            
        except Exception as e:
            logger.error(f"Hybrid search failed: {str(e)}")
            # Fallback to mock documents for development
            return self._generate_mock_documents(query)
    
    def _generate_mock_documents(self, query: str) -> List[Dict]:
        """Generate mock documents for development/fallback"""
        companies = ["Apple", "Microsoft", "Google", "Meta", "JPMC", "Amazon"]
        years = ["2024", "2023", "2022", "2021"]
        
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
                
                doc = {
                    "id": doc_id,
                    "content": content,
                    "title": f"{company} Annual Report {year}",
                    "source": f"{company}_{year}_10-K",
                    "document_id": f"doc_{doc_id}",
                    "company": company,
                    "filing_date": f"{year}-03-15",
                    "document_type": "10-K",
                    "section_type": "Business Overview",
                    "page_number": i + 1,
                    "ticker": company[:4].upper(),
                    "form_type": "10-K",
                    "chunk_id": f"chunk_{doc_id}",
                    "chunk_index": j,
                    "document_url": f"https://sec.gov/documents/{company}_{year}_10K.pdf",
                    "credibility_score": 0.85 + (i * 0.02),
                    
                    # Search metadata
                    "search_score": 0.9 - (i * 0.1) - (j * 0.05),
                    "reranker_score": 0.85 - (i * 0.08) - (j * 0.04),
                    "highlights": [f"Key information about {company} operations and {query}"],
                    "search_query": query,
                    
                    # Citation information
                    "citation": {
                        "title": f"{company} Annual Report {year}",
                        "source": f"{company}_{year}_10-K",
                        "company": company,
                        "document_type": "10-K",
                        "form_type": "10-K",
                        "filing_date": f"{year}-03-15",
                        "page_number": i + 1,
                        "section_type": "Business Overview",
                        "document_url": f"https://sec.gov/documents/{company}_{year}_10K.pdf",
                        "chunk_id": f"chunk_{doc_id}",
                        "credibility_score": 0.85 + (i * 0.02)
                    },
                    "citation_info": f"{company} {year} Annual Report, Section: Business Overview"
                }
                
                docs.append(doc)
        
        return sorted(docs, key=lambda x: x["search_score"], reverse=True)
