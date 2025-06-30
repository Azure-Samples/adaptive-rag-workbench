"""Tests for chat API endpoints."""

import pytest
import json
from unittest.mock import Mock, patch, AsyncMock
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


@patch('app.api.chat.orchestrator')
def test_chat_stream_success(mock_orchestrator):
    """Test successful chat streaming."""
    # Mock plan creation
    mock_orchestrator.create_plan = AsyncMock(return_value=["RetrieverAgent", "WriterAgent"])
    
    # Mock streaming response
    async def mock_run_stream(prompt, plan):
        yield "Hello "
        yield "world!"
    
    mock_orchestrator.run_stream = mock_run_stream
    
    response = client.post(
        "/api/chat",
        json={"prompt": "Test query", "mode": "context-aware-generation"}
    )
    
    assert response.status_code == 200
    assert response.headers["content-type"] == "text/event-stream; charset=utf-8"
    
    # Check that response contains streaming data
    content = response.text
    assert "data:" in content


@patch('app.api.chat.orchestrator')
def test_chat_stream_default_mode(mock_orchestrator):
    """Test chat with default mode."""
    mock_orchestrator.create_plan = AsyncMock(return_value=["RetrieverAgent", "WriterAgent"])
    
    async def mock_run_stream(prompt, plan):
        yield "Response"
    
    mock_orchestrator.run_stream = mock_run_stream
    
    response = client.post(
        "/api/chat",
        json={"prompt": "Test query"}  # No mode specified
    )
    
    assert response.status_code == 200
    mock_orchestrator.create_plan.assert_called_once_with({"mode": "context-aware-generation"})


@patch('app.api.chat.orchestrator')
def test_chat_stream_qa_verification_mode(mock_orchestrator):
    """Test chat with QA verification mode."""
    mock_orchestrator.create_plan = AsyncMock(return_value=["RetrieverAgent", "VerifierAgent", "WriterAgent"])
    
    async def mock_run_stream(prompt, plan):
        yield "Verified response"
    
    mock_orchestrator.run_stream = mock_run_stream
    
    response = client.post(
        "/api/chat",
        json={"prompt": "Compare companies", "mode": "qa-verification"}
    )
    
    assert response.status_code == 200
    mock_orchestrator.create_plan.assert_called_once_with({"mode": "qa-verification"})


@patch('app.api.chat.orchestrator')
def test_chat_stream_plan_creation_error(mock_orchestrator):
    """Test error handling when plan creation fails."""
    mock_orchestrator.create_plan = AsyncMock(side_effect=Exception("Plan creation failed"))
    
    response = client.post(
        "/api/chat",
        json={"prompt": "Test query"}
    )
    
    assert response.status_code == 500
    assert "Plan creation failed" in response.json()["detail"]


@patch('app.api.chat.orchestrator')
def test_chat_stream_execution_error(mock_orchestrator):
    """Test error handling during stream execution."""
    mock_orchestrator.create_plan = AsyncMock(return_value=["RetrieverAgent", "WriterAgent"])
    
    async def mock_run_stream_error(prompt, plan):
        yield "Starting..."
        raise Exception("Stream processing failed")
    
    mock_orchestrator.run_stream = mock_run_stream_error
    
    response = client.post(
        "/api/chat",
        json={"prompt": "Test query"}
    )
    
    assert response.status_code == 200  # Stream starts successfully
    content = response.text
    assert "Starting..." in content  # Initial content is sent
    assert "Stream processing failed" in content  # Error is captured in stream


def test_chat_invalid_request():
    """Test chat endpoint with invalid request data."""
    response = client.post("/api/chat", json={})  # Missing prompt
    
    assert response.status_code == 422  # Validation error


def test_chat_empty_prompt():
    """Test chat endpoint with empty prompt."""
    response = client.post(
        "/api/chat",
        json={"prompt": ""}
    )
    
    # Should accept empty prompt but may not produce meaningful results
    assert response.status_code == 200


@patch('app.api.chat.orchestrator')
def test_chat_stream_response_format(mock_orchestrator):
    """Test that stream response has correct format."""
    mock_orchestrator.create_plan = AsyncMock(return_value=["RetrieverAgent", "WriterAgent"])
    
    async def mock_run_stream(prompt, plan):
        yield "token1"
        yield "token2"
    
    mock_orchestrator.run_stream = mock_run_stream
    
    response = client.post(
        "/api/chat",
        json={"prompt": "Test query"}
    )
    
    assert response.status_code == 200
    content = response.text
    
    # Check that response contains proper SSE format
    lines = content.strip().split('\n')
    data_lines = [line for line in lines if line.startswith('data:')]
    
    assert len(data_lines) >= 2  # At least token responses + done signal
    
    # Check that we can parse the JSON data
    for line in data_lines[:-1]:  # Exclude the last 'done' line
        json_data = json.loads(line[5:])  # Remove 'data:' prefix
        if 'token' in json_data:
            assert isinstance(json_data['token'], str)
    
    # Last line should be done signal
    last_data = json.loads(data_lines[-1][5:])
    assert 'done' in last_data
    assert last_data['done'] is True