"""Tests for configuration module."""

import pytest
import os
from unittest.mock import patch
from app.core.config import Settings


def test_settings_defaults():
    """Test default settings values."""
    settings = Settings()
    
    assert settings.openai_endpoint == ""
    assert settings.openai_key == ""
    assert settings.openai_chat_deployment == "gpt-4o-mini"
    assert settings.openai_embed_deployment == "text-embedding-3-small"
    assert settings.search_endpoint == ""
    assert settings.search_admin_key == ""
    assert settings.search_index == "filings"
    assert settings.foundry_endpoint is None
    assert settings.foundry_api_key is None
    assert settings.document_intel_account_url == ""
    assert settings.document_intel_key == ""


def test_settings_from_env():
    """Test settings load from environment variables."""
    with patch.dict(os.environ, {
        'OPENAI_ENDPOINT': 'https://test.openai.azure.com/',
        'OPENAI_KEY': 'test-key',
        'SEARCH_ENDPOINT': 'https://test.search.windows.net',
        'SEARCH_ADMIN_KEY': 'search-key',
        'SEARCH_INDEX': 'test-index',
        'DOCUMENT_INTEL_ACCOUNT_URL': 'https://test.cognitiveservices.azure.com/',
        'DOCUMENT_INTEL_KEY': 'di-key'
    }):
        settings = Settings()
        
        assert settings.openai_endpoint == 'https://test.openai.azure.com/'
        assert settings.openai_key == 'test-key'
        assert settings.search_endpoint == 'https://test.search.windows.net'
        assert settings.search_admin_key == 'search-key'
        assert settings.search_index == 'test-index'
        assert settings.document_intel_account_url == 'https://test.cognitiveservices.azure.com/'
        assert settings.document_intel_key == 'di-key'


def test_settings_custom_deployment_names():
    """Test custom OpenAI deployment names."""
    with patch.dict(os.environ, {
        'OPENAI_CHAT_DEPLOYMENT': 'gpt-4',
        'OPENAI_EMBED_DEPLOYMENT': 'text-embedding-ada-002',
    }):
        settings = Settings()
        
        assert settings.openai_chat_deployment == 'gpt-4'
        assert settings.openai_embed_deployment == 'text-embedding-ada-002'


def test_settings_optional_foundry():
    """Test optional Foundry settings."""
    with patch.dict(os.environ, {
        'FOUNDRY_ENDPOINT': 'https://test.foundry.com',
        'FOUNDRY_API_KEY': 'foundry-key'
    }):
        settings = Settings()
        
        assert settings.foundry_endpoint == 'https://test.foundry.com'
        assert settings.foundry_api_key == 'foundry-key'