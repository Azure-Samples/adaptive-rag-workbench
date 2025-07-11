import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from app.agents.retriever import RetrieverAgent
from app.core.config import settings


class TestRetrieverAgent:
    """Test suite for RetrieverAgent with hybrid vector search"""
    
    @pytest.fixture
    def mock_kernel(self):
        """Mock Semantic Kernel"""
        return MagicMock()
    
    @pytest.fixture
    def mock_search_client(self):
        """Mock Azure Search client"""
        return MagicMock()
    
    @pytest.fixture
    def mock_openai_client(self):
        """Mock Azure OpenAI client"""
        client = AsyncMock()
        client.embeddings.create.return_value = MagicMock(
            data=[MagicMock(embedding=[0.1] * 1536)]
        )
        return client
    
    @pytest.fixture
    def retriever_agent(self, mock_kernel, mock_search_client, mock_openai_client):
        """Create RetrieverAgent with mocked dependencies"""
        with patch('app.agents.retriever.SearchClient', return_value=mock_search_client), \
             patch('app.agents.retriever.AsyncAzureOpenAI', return_value=mock_openai_client):
            agent = RetrieverAgent(mock_kernel)
            agent.search_client = mock_search_client
            agent.openai_client = mock_openai_client
            return agent
    
    @pytest.mark.asyncio
    async def test_query_embedding_generation(self, retriever_agent):
        """Test query embedding generation"""
        query = "What are the main risk factors for tech companies?"
        
        # Test successful embedding generation
        embedding = await retriever_agent._generate_query_embedding(query)
        assert embedding is not None
        assert len(embedding) == 1536
        assert all(isinstance(val, float) for val in embedding)
        
        # Test embedding generation failure
        retriever_agent.openai_client.embeddings.create.side_effect = Exception("API Error")
        embedding = await retriever_agent._generate_query_embedding(query)
        assert embedding is None
    
    @pytest.mark.asyncio
    async def test_hybrid_search_success(self, retriever_agent, mock_search_client):
        """Test successful hybrid search execution"""
        query = "revenue growth strategies"
        
        # Mock search results
        mock_result = MagicMock()
        mock_result.get.side_effect = lambda key, default=None: {
            "id": "doc1",
            "content": "Revenue growth was driven by strong performance in key segments.",
            "title": "Microsoft Annual Report 2024",
            "source": "Microsoft_2024_10-K",
            "company": "Microsoft",
            "filing_date": "2024-03-15",
            "document_type": "10-K",
            "section_type": "Financial Performance",
            "page_number": 25,
            "ticker": "MSFT",
            "form_type": "10-K",
            "chunk_id": "chunk_doc1",
            "chunk_index": 1,
            "document_url": "https://sec.gov/documents/Microsoft_2024_10K.pdf",
            "credibility_score": 0.92,
            "@search.score": 0.85,
            "@search.reranker_score": 0.78,
            "@search.captions": [{"text": "Revenue growth was driven by strong performance"}]
        }.get(key, default)
        
        mock_search_client.search.return_value = [mock_result]
        
        # Execute search
        results = await retriever_agent.invoke(query)
        
        # Verify results
        assert len(results) == 1
        doc = results[0]
        
        # Check document structure
        assert doc["id"] == "doc1"
        assert doc["content"] == "Revenue growth was driven by strong performance in key segments."
        assert doc["title"] == "Microsoft Annual Report 2024"
        assert doc["company"] == "Microsoft"
        assert doc["search_score"] == 0.85
        assert doc["reranker_score"] == 0.78
        assert doc["search_query"] == query
        assert "citation" in doc
        assert doc["citation"]["company"] == "Microsoft"
        
        # Verify search client was called with correct parameters
        mock_search_client.search.assert_called_once()
        call_args = mock_search_client.search.call_args
        assert call_args[1]["search_text"] == query
        assert call_args[1]["top"] == 10
        assert "vector_queries" in call_args[1]
    
    @pytest.mark.asyncio
    async def test_search_with_explicit_filters(self, retriever_agent, mock_search_client):
        """Test search with explicitly provided filters"""
        query = "AI strategy"
        filters = {"company": "Microsoft", "document_type": "10-K"}
        
        mock_search_client.search.return_value = []
        
        await retriever_agent.invoke(query, filters=filters)
        
        # Verify filter was applied
        call_args = mock_search_client.search.call_args
        assert "filter" in call_args[1]
        filter_expr = call_args[1]["filter"]
        assert "company eq 'Microsoft'" in filter_expr
        assert "document_type eq '10-K'" in filter_expr
    
    @pytest.mark.asyncio
    async def test_search_with_custom_top_k(self, retriever_agent, mock_search_client):
        """Test search with custom top_k parameter"""
        query = "cloud computing revenue"
        top_k = 5
        
        mock_search_client.search.return_value = []
        
        await retriever_agent.invoke(query, top_k=top_k)
        
        # Verify top_k was applied
        call_args = mock_search_client.search.call_args
        assert call_args[1]["top"] == top_k
    
    @pytest.mark.asyncio
    async def test_score_filtering(self, retriever_agent, mock_search_client):
        """Test that results are filtered by score thresholds"""
        query = "financial performance"
        
        # Create mock results with different scores
        high_score_result = MagicMock()
        high_score_result.get.side_effect = lambda key, default=None: {
            "id": "doc1",
            "content": "High relevance content",
            "@search.score": 0.8,
            "@search.reranker_score": 0.75,
            "title": "High Score Doc",
            "source": "test_source",
            "company": "TestCorp"
        }.get(key, default)
        
        low_score_result = MagicMock()
        low_score_result.get.side_effect = lambda key, default=None: {
            "id": "doc2",
            "content": "Low relevance content",
            "@search.score": 0.3,  # Below threshold
            "@search.reranker_score": 0.25,
            "title": "Low Score Doc",
            "source": "test_source",
            "company": "TestCorp"
        }.get(key, default)
        
        mock_search_client.search.return_value = [high_score_result, low_score_result]
        
        results = await retriever_agent.invoke(query)
        
        # Only high score result should be returned
        assert len(results) == 1
        assert results[0]["id"] == "doc1"
        assert results[0]["search_score"] == 0.8
    
    @pytest.mark.asyncio
    async def test_fallback_to_mock_documents(self, retriever_agent, mock_search_client):
        """Test fallback to mock documents when search fails"""
        query = "risk factors"
        
        # Simulate search failure
        mock_search_client.search.side_effect = Exception("Search service unavailable")
        
        results = await retriever_agent.invoke(query)
        
        # Should return mock documents
        assert len(results) > 0
        assert all("citation" in doc for doc in results)
        assert all("search_score" in doc for doc in results)
        assert results[0]["search_query"] == query
    
    @pytest.mark.asyncio
    async def test_get_response_formatting(self, retriever_agent, mock_search_client):
        """Test formatted response generation"""
        query = "revenue analysis"
        
        # Mock a single result
        mock_result = MagicMock()
        mock_result.get.side_effect = lambda key, default=None: {
            "id": "doc1",
            "content": "Revenue analysis content",
            "title": "Financial Report",
            "company": "TestCorp",
            "document_type": "10-K",
            "@search.score": 0.85,
            "source": "test_source"
        }.get(key, default)
        
        mock_search_client.search.return_value = [mock_result]
        
        response = await retriever_agent.get_response(query)
        
        assert "Retrieved 1 relevant documents" in response
        assert "Financial Report" in response
        assert "TestCorp" in response
        assert "10-K" in response
        assert "0.850" in response
    
    @pytest.mark.asyncio
    async def test_streaming_response(self, retriever_agent, mock_search_client):
        """Test streaming response generation"""
        query = "market analysis"
        
        # Mock result for streaming
        mock_result = MagicMock()
        mock_result.get.side_effect = lambda key, default=None: {
            "id": "doc1",
            "content": "Market analysis shows strong growth trends in cloud computing.",
            "title": "Market Analysis Report",
            "company": "TechCorp",
            "document_type": "Quarterly Report",
            "@search.score": 0.88,
            "source": "quarterly_report_2024",
            "@search.captions": [{"text": "strong growth trends in cloud computing"}]
        }.get(key, default)
        
        mock_search_client.search.return_value = [mock_result]
        
        # Collect streaming chunks
        chunks = []
        async for chunk in retriever_agent.invoke_stream(query):
            chunks.append(chunk)
        
        full_response = "".join(chunks)
        
        assert "🔍 Searching for: market analysis" in full_response
        assert "📊 Found 1 relevant documents" in full_response
        assert "📄 Document 1: Market Analysis Report" in full_response
        assert "🏢 Company: TechCorp" in full_response
        assert "📋 Type: Quarterly Report" in full_response
        assert "⭐ Score: 0.880" in full_response
        assert "🎯 Key excerpts:" in full_response
        assert "strong growth trends in cloud computing" in full_response
    
    @pytest.mark.asyncio
    async def test_citation_building(self, retriever_agent):
        """Test citation information building"""
        result = {
            "title": "Microsoft Annual Report 2024",
            "source": "Microsoft_2024_10-K",
            "company": "Microsoft",
            "document_type": "10-K",
            "form_type": "10-K",
            "filing_date": "2024-03-15",
            "page_number": 42,
            "section_type": "Risk Factors",
            "document_url": "https://sec.gov/documents/Microsoft_2024_10K.pdf",
            "chunk_id": "chunk_001",
            "credibility_score": 0.89
        }
        
        citation = retriever_agent._build_citation(result)
        
        assert citation["title"] == "Microsoft Annual Report 2024"
        assert citation["company"] == "Microsoft"
        assert citation["document_type"] == "10-K"
        assert citation["page_number"] == 42
        assert citation["credibility_score"] == 0.89
        assert citation["document_url"] == "https://sec.gov/documents/Microsoft_2024_10K.pdf"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
