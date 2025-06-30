"""Tests for agent tools module."""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from app.agents.tools import SearchTools


@pytest.fixture
def mock_settings():
    """Mock settings for testing."""
    with patch('app.agents.tools.settings') as mock:
        mock.search_endpoint = "https://test.search.windows.net"
        mock.search_index = "test-index"
        mock.search_admin_key = "test-key"
        yield mock


@pytest.fixture
def search_tools(mock_settings):
    """Create SearchTools instance with mocked settings."""
    with patch('app.agents.tools.SearchClient') as mock_client:
        mock_client_instance = Mock()
        mock_client.return_value = mock_client_instance
        tools = SearchTools()
        tools.search_client = mock_client_instance
        yield tools


@pytest.mark.asyncio
async def test_search_documents_success(search_tools):
    """Test successful document search."""
    # Mock search results with correct field names
    mock_results = [
        {
            "content_text": "Apple Inc. reported revenue of $365 billion",
            "document_title": "Apple 10-K 2023",
            "content_path": "/apple/2023/10k.pdf",
            "company": "Apple",
            "year": 2023,
            "@search.score": 0.95,
            "@search.reranker_score": 0.92
        },
        {
            "content_text": "Microsoft's cloud revenue grew 25%",
            "document_title": "Microsoft 10-K 2023", 
            "content_path": "/microsoft/2023/10k.pdf",
            "company": "Microsoft",
            "year": 2023,
            "@search.score": 0.88
        }
    ]
    
    search_tools.search_client.search.return_value = mock_results
    
    result = await search_tools.search_documents("revenue growth", top=5)
    
    assert isinstance(result, str)
    assert "Apple Inc. reported revenue" in result
    assert "Microsoft's cloud revenue" in result
    assert "Apple 10-K 2023" in result
    assert "0.920" in result  # First doc reranker score  
    assert "0.000" in result  # Second doc shows 0.000 when no reranker score
    
    # Verify search was called with correct parameters
    search_tools.search_client.search.assert_called_once()
    call_args = search_tools.search_client.search.call_args
    assert call_args[1]["search_text"] == "revenue growth"
    assert call_args[1]["top"] == 5


@pytest.mark.asyncio
async def test_search_documents_default_top(search_tools):
    """Test search with default top parameter."""
    search_tools.search_client.search.return_value = []
    
    await search_tools.search_documents("test query")
    
    call_args = search_tools.search_client.search.call_args
    assert call_args[1]["top"] == 10  # Default value


@pytest.mark.asyncio
async def test_search_documents_semantic_search_params(search_tools):
    """Test that semantic search parameters are set correctly."""
    search_tools.search_client.search.return_value = []
    
    await search_tools.search_documents("test query")
    
    call_args = search_tools.search_client.search.call_args
    assert "query_type" in call_args[1]
    assert "semantic_configuration_name" in call_args[1]
    assert "query_caption" in call_args[1]
    assert "semantic_query" in call_args[1]
    assert call_args[1]["semantic_query"] == "test query"


@pytest.mark.asyncio
async def test_search_documents_empty_results(search_tools):
    """Test search with no results."""
    search_tools.search_client.search.return_value = []
    
    result = await search_tools.search_documents("nonexistent query")
    
    assert result == ""  # Should return empty string


@pytest.mark.asyncio
async def test_search_documents_missing_fields(search_tools):
    """Test search with documents missing some fields."""
    mock_results = [
        {
            "content_text": "Some content",
            # Missing other fields
        }
    ]
    
    search_tools.search_client.search.return_value = mock_results
    
    result = await search_tools.search_documents("test query")
    
    assert "Some content" in result
    # Should handle missing fields gracefully


@pytest.mark.asyncio
async def test_search_documents_exception_handling(search_tools):
    """Test error handling in search."""
    search_tools.search_client.search.side_effect = Exception("Connection failed")
    
    result = await search_tools.search_documents("test query")
    
    assert result.startswith("Search error:")
    assert "Connection failed" in result


@pytest.mark.asyncio
async def test_search_documents_special_characters(search_tools):
    """Test search with special characters in query."""
    search_tools.search_client.search.return_value = []
    
    special_query = "R&D costs: $1,000+ (2023)"
    result = await search_tools.search_documents(special_query)
    
    # Should not raise exception
    assert isinstance(result, str)
    
    call_args = search_tools.search_client.search.call_args
    assert call_args[1]["search_text"] == special_query


def test_search_tools_initialization(mock_settings):
    """Test SearchTools initialization."""
    with patch('app.agents.tools.SearchClient') as mock_client_class:
        mock_client_class.return_value = Mock()
        
        tools = SearchTools()
        
        # Verify SearchClient was initialized with correct parameters
        mock_client_class.assert_called_once()
        call_args = mock_client_class.call_args
        assert call_args[1]["endpoint"] == "https://test.search.windows.net"
        assert call_args[1]["index_name"] == "test-index"


def test_search_tools_kernel_function_metadata():
    """Test that search_documents has proper kernel function metadata."""
    from semantic_kernel.functions import kernel_function
    
    # Check that the function is decorated
    assert hasattr(SearchTools.search_documents, '__kernel_function__')
    
    # The function should have metadata for Semantic Kernel
    func = SearchTools.search_documents
    assert func.__name__ == "search_documents"