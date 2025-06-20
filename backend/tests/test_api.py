import pytest
import json
from unittest.mock import Mock, patch, AsyncMock
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_healthz():
    """Test health check endpoint."""
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

def test_root():
    """Test root endpoint."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "Adaptive RAG Workbench API" in data["message"]
    assert "version" in data
    assert data["version"] == "1.0.0"

@patch('azure.search.documents.SearchClient')
def test_index_stats_with_mock(mock_search_client):
    """Test index stats endpoint with mocked Azure Search."""
    mock_client_instance = Mock()
    mock_search_client.return_value = mock_client_instance
    
    # Mock search results
    mock_results = Mock()
    mock_results.get_count.return_value = 1500
    mock_client_instance.search.return_value = mock_results
    
    # Mock facets  
    mock_facet_results = Mock()
    mock_facets = {
        'company': [
            {'value': 'Apple', 'count': 300},
            {'value': 'Microsoft', 'count': 400}
        ]
    }
    mock_facet_results.get_facets.return_value = mock_facets
    
    # Set up mock to return different results for different calls
    mock_client_instance.search.side_effect = [mock_results, mock_facet_results]
    
    response = client.get("/api/index-stats")
    assert response.status_code == 200
    
    data = response.json()
    assert "total_documents" in data
    assert "company_breakdown" in data
    assert isinstance(data["total_documents"], int)
    assert data["total_documents"] == 1500

def test_index_stats_fallback():
    """Test index stats endpoint falls back to mock data on error."""
    with patch('azure.search.documents.SearchClient', side_effect=Exception("Connection error")):
        response = client.get("/api/index-stats")
        assert response.status_code == 200
        
        data = response.json()
        assert data["total_documents"] == 2847  # Mock fallback value
        assert "Apple" in data["company_breakdown"]
        assert "Microsoft" in data["company_breakdown"]

@patch('app.api.ingest.CuratorAgent')
@patch('app.api.ingest.Kernel')
def test_upload_file_success(mock_kernel, mock_curator_agent):
    """Test successful file upload."""
    # Mock curator agent
    mock_curator_instance = Mock()
    mock_curator_agent.return_value = mock_curator_instance
    
    # Mock streaming response
    async def mock_invoke_stream(file_path):
        yield "Processing started...\n"
        yield "Document processed successfully\n"
    
    mock_curator_instance.invoke_stream = mock_invoke_stream
    
    # Create test file content
    test_content = b"This is a test PDF content"
    
    response = client.post(
        "/api/upload",
        files={"file": ("test.pdf", test_content, "application/pdf")}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["filename"] == "test.pdf"
    assert "Processing started" in data["message"]

def test_upload_file_no_filename():
    """Test upload endpoint with missing filename."""
    response = client.post(
        "/api/upload",
        files={"file": ("", b"content", "application/pdf")}
    )
    
    assert response.status_code == 422  # FastAPI validation error for missing filename

@patch('app.api.ingest.CuratorAgent')
@patch('app.api.ingest.Kernel')
def test_upload_file_processing_error(mock_kernel, mock_curator_agent):
    """Test upload endpoint when processing fails."""
    # Mock curator agent to raise exception
    mock_curator_instance = Mock()
    mock_curator_agent.return_value = mock_curator_instance
    
    async def mock_invoke_stream_error(file_path):
        if False:  # Make this a proper async generator
            yield "dummy"
        raise Exception("Processing failed")
    
    mock_curator_instance.invoke_stream = mock_invoke_stream_error
    
    test_content = b"This is a test PDF content"
    
    response = client.post(
        "/api/upload",
        files={"file": ("test.pdf", test_content, "application/pdf")}
    )
    
    assert response.status_code == 500
    # The error message might be different due to async handling
    assert "error" in response.json()["detail"].lower() or "fail" in response.json()["detail"].lower()
