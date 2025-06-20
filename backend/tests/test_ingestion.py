"""Tests for ingestion modules."""

import pytest
import hashlib
from unittest.mock import Mock, patch, mock_open, AsyncMock
from pathlib import Path


@patch('app.ingestion.chunk.tiktoken.get_encoding')
def test_chunk_document_basic(mock_get_encoding):
    """Test basic document chunking functionality."""
    from app.ingestion.chunk import chunk_document
    
    # Mock tiktoken encoding
    mock_enc = Mock()
    mock_enc.encode.return_value = list(range(100))  # Mock 100 tokens
    # Mock decode to return a valid chunk with sufficient length
    mock_enc.decode.return_value = "This is a test document chunk with enough content to be valid for processing."
    mock_get_encoding.return_value = mock_enc
    
    text = "This is a test document. " * 100  # Create a longer text
    
    chunks = list(chunk_document(text, size=50, overlap=10, company="TestCorp", year=2024))
    
    assert len(chunks) > 0
    
    # Check first chunk structure
    first_chunk = chunks[0]
    assert "id" in first_chunk
    assert "content" in first_chunk
    assert "source" in first_chunk
    assert "company" in first_chunk
    assert "year" in first_chunk
    
    assert first_chunk["company"] == "TestCorp"
    assert first_chunk["year"] == 2024
    assert first_chunk["source"] == "TestCorp_2024_10-K"


@patch('app.ingestion.chunk.tiktoken.get_encoding')
def test_chunk_document_overlap(mock_get_encoding):
    """Test that chunking creates proper overlap."""
    from app.ingestion.chunk import chunk_document
    
    # Mock tiktoken encoding
    mock_enc = Mock()
    mock_enc.encode.return_value = list(range(50))  # Mock 50 tokens
    # Use a function that returns different values but doesn't run out
    def mock_decode(tokens):
        return f"Chunk with content {len(tokens)} tokens - enough content to be valid for processing."
    mock_enc.decode.side_effect = mock_decode
    mock_get_encoding.return_value = mock_enc
    
    text = "Word1 Word2 Word3 Word4 Word5 Word6 Word7 Word8 Word9 Word10 " * 10
    
    chunks = list(chunk_document(text, size=10, overlap=3, company="Test", year=2024))
    
    assert len(chunks) >= 2  # Should create multiple chunks


@patch('app.ingestion.chunk.tiktoken.get_encoding')
def test_chunk_document_short_content_filtered(mock_get_encoding):
    """Test that very short chunks are filtered out."""
    from app.ingestion.chunk import chunk_document
    
    # Mock tiktoken encoding for short content
    mock_enc = Mock()
    mock_enc.encode.return_value = [1, 2, 3]  # Very few tokens
    mock_enc.decode.return_value = "Short"  # Less than 50 chars
    mock_get_encoding.return_value = mock_enc
    
    text = "Short"
    
    chunks = list(chunk_document(text, size=1000, overlap=20, company="Test", year=2024))
    
    # Should be empty because content is too short (< 50 chars after stripping)
    assert len(chunks) == 0


@patch('app.ingestion.chunk.tiktoken.get_encoding')
def test_chunk_document_unique_ids(mock_get_encoding):
    """Test that chunk IDs are unique and deterministic."""
    from app.ingestion.chunk import chunk_document
    
    # Mock tiktoken encoding
    mock_enc = Mock()
    mock_enc.encode.return_value = list(range(200))  # Mock 200 tokens
    # Use a function for decode that always returns valid content
    def mock_decode(tokens):
        # Generate different content based on token range start
        token_start = tokens[0] if tokens else 0
        return f"This is chunk {token_start} with enough content to be valid for processing and testing purposes."
    mock_enc.decode.side_effect = mock_decode
    mock_get_encoding.return_value = mock_enc
    
    text = "This is a test document with enough content to create multiple chunks. " * 20
    
    chunks = list(chunk_document(text, size=50, overlap=10, company="TestCorp", year=2024))
    
    # Get all IDs
    chunk_ids = [chunk["id"] for chunk in chunks]
    
    # Check that all IDs are unique
    assert len(chunk_ids) == len(set(chunk_ids))
    
    # Test deterministic ID generation
    expected_first_id = hashlib.md5(f"TestCorp_2024_{chunks[0]['content']}".encode()).hexdigest()
    assert chunks[0]["id"] == expected_first_id


@patch('app.ingestion.chunk.tiktoken.get_encoding')
def test_chunk_document_empty_text(mock_get_encoding):
    """Test chunking with empty text."""
    from app.ingestion.chunk import chunk_document
    
    # Mock tiktoken encoding for empty content
    mock_enc = Mock()
    mock_enc.encode.return_value = []  # No tokens
    mock_get_encoding.return_value = mock_enc
    
    chunks = list(chunk_document("", size=100, overlap=20, company="Test", year=2024))
    
    assert len(chunks) == 0


@patch('app.ingestion.chunk.tiktoken.get_encoding')
def test_chunk_document_different_companies(mock_get_encoding):
    """Test that different companies produce different chunk IDs."""
    from app.ingestion.chunk import chunk_document
    
    # Mock tiktoken encoding
    mock_enc = Mock()
    mock_enc.encode.return_value = list(range(100))  # Mock tokens
    mock_enc.decode.return_value = "This is a test document with enough content to be chunked properly."
    mock_get_encoding.return_value = mock_enc
    
    text = "This is a test document with enough content to be chunked properly."
    
    chunks_a = list(chunk_document(text, size=100, overlap=20, company="CompanyA", year=2024))
    chunks_b = list(chunk_document(text, size=100, overlap=20, company="CompanyB", year=2024))
    
    assert len(chunks_a) > 0
    assert len(chunks_b) > 0
    assert chunks_a[0]["id"] != chunks_b[0]["id"]
    assert chunks_a[0]["company"] != chunks_b[0]["company"]


# Tests for document extraction functionality


@pytest.mark.asyncio
@patch('app.ingestion.di_extract.DocumentIntelligenceClient')
async def test_extract_pdf_content_success(mock_client_class):
    """Test successful PDF content extraction."""
    from app.ingestion.di_extract import extract_pdf_content
    
    # Mock client and result
    mock_client = Mock()
    mock_client_class.return_value = mock_client
    
    mock_result = Mock()
    mock_result.to_dict.return_value = {
        "content": "Extracted PDF text",
        "pages": [{"page_number": 1}]
    }
    
    mock_poller = Mock()
    mock_poller.result.return_value = mock_result
    mock_client.begin_analyze_document.return_value = mock_poller
    
    # Create test file
    test_file = Path("/tmp/test.pdf")
    
    with patch("builtins.open", mock_open(read_data=b"PDF content")):
        result = await extract_pdf_content(test_file)
        
        assert "content" in result
        assert result["content"] == "Extracted PDF text"
        mock_client.begin_analyze_document.assert_called_once_with("prebuilt-layout", b"PDF content")


@pytest.mark.asyncio  
@patch('app.ingestion.di_extract.DocumentIntelligenceClient')
async def test_extract_pdf_content_error(mock_client_class):
    """Test PDF extraction error handling."""
    from app.ingestion.di_extract import extract_pdf_content
    
    # Mock client to raise exception
    mock_client_class.side_effect = Exception("Service unavailable")
    
    test_file = Path("/tmp/test.pdf")
    
    with patch("builtins.open", mock_open(read_data=b"PDF content")):
        result = await extract_pdf_content(test_file)
        
        assert "content" in result
        assert "Error extracting content" in result["content"]
        assert "Service unavailable" in result["content"]


@pytest.mark.asyncio
async def test_extract_html_content_success():
    """Test successful HTML content extraction."""
    from app.ingestion.di_extract import extract_html_content
    
    html_content = """
    <html>
        <head><title>Test Document</title></head>
        <body>
            <h1>Main Heading</h1>
            <p>This is the main content of the document.</p>
            <script>console.log('remove me');</script>
            <style>.hidden { display: none; }</style>
        </body>
    </html>
    """
    
    test_file = Path("/tmp/test.html")
    
    with patch("builtins.open", mock_open(read_data=html_content)):
        result = await extract_html_content(test_file)
        
        assert "content" in result
        content = result["content"]
        assert "Main Heading" in content
        assert "main content of the document" in content
        assert "console.log" not in content  # Script should be removed
        assert ".hidden" not in content  # Style should be removed


@pytest.mark.asyncio
async def test_extract_html_content_complex():
    """Test HTML extraction with complex structure."""
    from app.ingestion.di_extract import extract_html_content
    
    html_content = """
    <html>
        <body>
            <div class="content">
                <h1>Financial Report</h1>
                <p>Revenue increased by <strong>15%</strong> this quarter.</p>
                <ul>
                    <li>Q1: $100M</li>
                    <li>Q2: $115M</li>
                </ul>
                <table>
                    <tr><th>Year</th><th>Revenue</th></tr>
                    <tr><td>2023</td><td>$450M</td></tr>
                </table>
            </div>
        </body>
    </html>
    """
    
    test_file = Path("/tmp/report.html")
    
    with patch("builtins.open", mock_open(read_data=html_content)):
        result = await extract_html_content(test_file)
        
        content = result["content"]
        assert "Financial Report" in content
        assert "Revenue increased by 15%" in content
        assert "Q1: $100M" in content
        assert "2023" in content
        assert "$450M" in content


@pytest.mark.asyncio
async def test_extract_html_content_file_error():
    """Test HTML extraction file reading error."""
    from app.ingestion.di_extract import extract_html_content
    
    test_file = Path("/tmp/nonexistent.html")
    
    with patch("builtins.open", side_effect=FileNotFoundError("File not found")):
        result = await extract_html_content(test_file)
        
        assert "content" in result
        assert "Error extracting content" in result["content"]
        assert "File not found" in result["content"]


@pytest.mark.asyncio
async def test_extract_html_content_parsing_error():
    """Test HTML extraction with malformed HTML."""
    from app.ingestion.di_extract import extract_html_content
    
    # This should still work as BeautifulSoup is quite forgiving
    malformed_html = "<html><body><h1>Unclosed tag<p>Content</body></html>"
    
    test_file = Path("/tmp/malformed.html")
    
    with patch("builtins.open", mock_open(read_data=malformed_html)):
        result = await extract_html_content(test_file)
        
        assert "content" in result
        content = result["content"]
        assert "Unclosed tag" in content
        assert "Content" in content


@pytest.mark.asyncio
async def test_extract_html_content_empty_file():
    """Test HTML extraction with empty file."""
    from app.ingestion.di_extract import extract_html_content
    
    test_file = Path("/tmp/empty.html")
    
    with patch("builtins.open", mock_open(read_data="")):
        result = await extract_html_content(test_file)
        
        assert "content" in result
        assert result["content"] == ""  # Should handle empty content gracefully