"""
Token Usage Tracking Service

This service provides comprehensive token usage tracking and analytics
for all AI operations across the application. It stores detailed usage
data for analytics and reporting.
"""

import logging
import time
import uuid
import os
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from enum import Enum

from app.core.config import settings

logger = logging.getLogger(__name__)

class ServiceType(str, Enum):
    """Service types for token usage tracking"""
    QA_SERVICE = "qa_service"
    CHAT_SERVICE = "chat_service"
    CONTEXT_AWARE_GENERATION = "context_aware_generation"
    QA_VERIFICATION = "qa_verification"
    ADAPTIVE_KB_MANAGEMENT = "adaptive_kb_management"
    FAST_RAG = "fast_rag"
    AGENTIC_RAG = "agentic_rag"
    DEEP_RESEARCH_RAG = "deep_research_rag"
    SEC_DOCS = "sec_docs"

class OperationType(str, Enum):
    """Operation types for detailed tracking"""
    SEARCH_QUERY = "search_query"
    ANSWER_GENERATION = "answer_generation"
    DOCUMENT_ANALYSIS = "document_analysis"
    CREDIBILITY_CHECK = "credibility_check"
    SUB_QUESTION_GENERATION = "sub_question_generation"
    RELEVANCE_EXPLANATION = "relevance_explanation"
    CHAT_COMPLETION = "chat_completion"
    EMBEDDING_GENERATION = "embedding_generation"
    QUESTION_DECOMPOSITION = "question_decomposition"
    SOURCE_VERIFICATION = "source_verification"
    QUERY_REWRITE = "query_rewrite"
    AGENTIC_RETRIEVAL = "agentic_retrieval"

@dataclass
class TokenUsageRecord:
    """Comprehensive token usage record"""
    # Unique identifiers
    record_id: str
    session_id: str
    user_id: Optional[str] = None
    
    # Timing information
    timestamp: Optional[datetime] = None
    request_start_time: Optional[float] = None
    request_end_time: Optional[float] = None
    duration_ms: Optional[float] = None
    
    # Service information
    service_type: Optional[ServiceType] = None
    operation_type: Optional[OperationType] = None
    endpoint: Optional[str] = None
    
    # Model information
    model_name: Optional[str] = None  # Display name (e.g., "GPT-4o")
    deployment_name: Optional[str] = None  # Azure deployment name (e.g., "chat4o")
    model_version: Optional[str] = None
    model_provider: str = "azure_openai"
    
    # Azure resource information
    azure_region: Optional[str] = None
    resource_group: Optional[str] = None
    azure_subscription_id: Optional[str] = None
    
    # Token usage details
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    
    # Cost information
    prompt_cost: float = 0.0
    completion_cost: float = 0.0
    total_cost: float = 0.0
    cost_currency: str = "USD"
    
    # Request context
    request_text: Optional[str] = None
    response_text: Optional[str] = None
    request_size_chars: int = 0
    response_size_chars: int = 0
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    
    # Business context
    verification_level: Optional[str] = None
    credibility_check_enabled: bool = False
    decomposition_enabled: bool = False
    rag_mode: Optional[str] = None
    
    # Result information
    success: bool = True
    error_message: Optional[str] = None
    http_status_code: int = 200
    
    # Additional metadata
    metadata: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now(timezone.utc)
        if self.record_id is None:
            self.record_id = str(uuid.uuid4())
        if self.total_tokens == 0:
            self.total_tokens = self.prompt_tokens + self.completion_tokens
        if self.total_cost == 0.0:
            self.total_cost = self.prompt_cost + self.completion_cost
        if self.metadata is None:
            self.metadata = {}
        if self.request_text and self.request_size_chars == 0:
            self.request_size_chars = len(self.request_text)
        if self.response_text and self.response_size_chars == 0:
            self.response_size_chars = len(self.response_text)

class TokenUsageTracker:
    """Token usage tracking service with in-memory storage"""
    
    def __init__(self):
        self._active_sessions: Dict[str, TokenUsageRecord] = {}
        self._stored_records: List[TokenUsageRecord] = []
        
        # Token pricing (per 1K tokens) - these should be updated based on current Azure OpenAI pricing
        self.token_pricing = {
            "gpt-4o": {"prompt": 0.005, "completion": 0.015},
            "gpt-4o-mini": {"prompt": 0.00015, "completion": 0.0006},
            "gpt-4": {"prompt": 0.03, "completion": 0.06},
            "gpt-35-turbo": {"prompt": 0.0015, "completion": 0.002},
            "text-embedding-3-small": {"prompt": 0.00002, "completion": 0.0},
            "text-embedding-3-large": {"prompt": 0.00013, "completion": 0.0},
            "text-embedding-ada-002": {"prompt": 0.0001, "completion": 0.0}
        }
    
    def start_tracking(self, 
                      session_id: str,
                      service_type: ServiceType,
                      operation_type: OperationType,
                      endpoint: Optional[str] = None,
                      user_id: Optional[str] = None,
                      **kwargs) -> str:
        """Start tracking a new token usage session"""
        
        record = TokenUsageRecord(
            record_id=str(uuid.uuid4()),
            session_id=session_id,
            user_id=user_id,
            service_type=service_type,
            operation_type=operation_type,
            endpoint=endpoint,
            request_start_time=time.time(),
            **kwargs
        )
        
        self._active_sessions[record.record_id] = record
        return record.record_id
    
    def update_model_info(self,
                         record_id: str,
                         model_name: Optional[str] = None,
                         deployment_name: Optional[str] = None,
                         model_version: Optional[str] = None,
                         temperature: Optional[float] = None,
                         max_tokens: Optional[int] = None):
        """Update model information for an active tracking session"""
        if record_id in self._active_sessions:
            record = self._active_sessions[record_id]
            if model_name:
                record.model_name = model_name
            if deployment_name:
                record.deployment_name = deployment_name
            if model_version:
                record.model_version = model_version
            if temperature is not None:
                record.temperature = temperature
            if max_tokens:
                record.max_tokens = max_tokens
    
    def update_request_context(self,
                              record_id: str,
                              request_size_chars: Optional[int] = None,
                              verification_level: Optional[str] = None,
                              credibility_check_enabled: Optional[bool] = None,
                              decomposition_enabled: Optional[bool] = None,
                              rag_mode: Optional[str] = None,
                              metadata: Optional[Dict[str, Any]] = None):
        """Update request context information"""
        if record_id in self._active_sessions:
            record = self._active_sessions[record_id]
            if request_size_chars is not None:
                record.request_size_chars = request_size_chars
            if verification_level:
                record.verification_level = verification_level
            if credibility_check_enabled is not None:
                record.credibility_check_enabled = credibility_check_enabled
            if decomposition_enabled is not None:
                record.decomposition_enabled = decomposition_enabled
            if rag_mode:
                record.rag_mode = rag_mode
            if metadata:
                if record.metadata is None:
                    record.metadata = {}
                record.metadata.update(metadata)
    
    def record_token_usage(self,
                          record_id: str,
                          prompt_tokens: int,
                          completion_tokens: int,
                          response_size_chars: Optional[int] = None,
                          success: bool = True,
                          error_message: Optional[str] = None,
                          http_status_code: int = 200) -> Optional[TokenUsageRecord]:
        """Record token usage and finalize the tracking session"""
        
        if record_id not in self._active_sessions:
            logger.warning(f"Token usage record {record_id} not found in active sessions")
            return None
        
        record = self._active_sessions[record_id]
        
        # Update token usage
        record.prompt_tokens = prompt_tokens
        record.completion_tokens = completion_tokens
        record.total_tokens = prompt_tokens + completion_tokens
        
        # Calculate costs
        model_identifier = record.model_name or record.deployment_name or ""
        model_key = self._get_model_key_for_pricing(model_identifier)
        if model_key in self.token_pricing:
            pricing = self.token_pricing[model_key]
            record.prompt_cost = (prompt_tokens / 1000) * pricing["prompt"]
            record.completion_cost = (completion_tokens / 1000) * pricing["completion"]
            record.total_cost = record.prompt_cost + record.completion_cost
        
        # Update timing and result information
        record.request_end_time = time.time()
        if record.request_start_time:
            record.duration_ms = (record.request_end_time - record.request_start_time) * 1000
        
        if response_size_chars is not None:
            record.response_size_chars = response_size_chars
        
        record.success = success
        record.error_message = error_message
        record.http_status_code = http_status_code
        
        # Add Azure resource information if available
        try:
            record.azure_region = getattr(settings, 'azure_region', None) or os.getenv('AZURE_REGION')
            record.azure_subscription_id = getattr(settings, 'azure_subscription_id', None) or os.getenv('AZURE_SUBSCRIPTION_ID')
        except Exception:
            pass
        
        del self._active_sessions[record_id]
        self._stored_records.append(record)
        
        return record

    def store_token_usage(self, record: TokenUsageRecord):
        """Store token usage record in memory"""
        try:
            logger.info(f"Storing token usage record {record.record_id}")
            self._stored_records.append(record)
            logger.info(f"Successfully stored token usage record {record.record_id}")
        except Exception as e:
            logger.error(f"Failed to store token usage record: {e}")
            raise
    
    def _get_model_key_for_pricing(self, model_identifier: str) -> str:
        """Map model identifier to pricing key"""
        if not model_identifier:
            return "gpt-4o-mini"  # Default fallback
        
        model_lower = model_identifier.lower()
        
        # Map deployment names and model names to pricing keys
        if "gpt-4o-mini" in model_lower or "chat4omini" in model_lower:
            return "gpt-4o-mini"
        elif "gpt-4o" in model_lower or "chat4o" in model_lower:
            return "gpt-4o"
        elif "gpt-4" in model_lower:
            return "gpt-4"
        elif "gpt-35-turbo" in model_lower or "gpt-3.5-turbo" in model_lower:
            return "gpt-35-turbo"
        elif "text-embedding-3-small" in model_lower:
            return "text-embedding-3-small"        
        elif "text-embedding-3-large" in model_lower:
            return "text-embedding-3-large"
        elif "text-embedding-ada-002" in model_lower:
            return "text-embedding-ada-002"
        
        return "gpt-4o-mini"  # Default fallback
    
    def get_token_usage_analytics(self, 
                                 start_date: Optional[datetime] = None,
                                 end_date: Optional[datetime] = None,
                                 service_type: Optional[ServiceType] = None,
                                 model_name: Optional[str] = None) -> Dict[str, Any]:
        """Get token usage analytics from stored records"""
        try:
            filtered_records = self._stored_records
            
            if start_date:
                filtered_records = [r for r in filtered_records if r.timestamp and r.timestamp >= start_date]
            
            if end_date:
                filtered_records = [r for r in filtered_records if r.timestamp and r.timestamp <= end_date]
            
            if service_type:
                filtered_records = [r for r in filtered_records if r.service_type == service_type]
            
            if model_name:
                filtered_records = [r for r in filtered_records if r.model_name == model_name or r.deployment_name == model_name]
            
            items = [asdict(record) for record in filtered_records]
            
            # Aggregate the results
            analytics = self._aggregate_token_usage(items)
            
            return analytics
            
        except Exception as e:
            logger.error(f"Failed to get token usage analytics: {e}")
            return {}
    
    def _aggregate_token_usage(self, items: List[Dict]) -> Dict[str, Any]:
        """Aggregate token usage data for analytics"""
        if not items:
            return {
                "total_requests": 0,
                "total_tokens": 0,
                "total_cost": 0.0,
                "by_service": {},
                "by_model": {},
                "by_date": {},
                "average_tokens_per_request": 0,
                "success_rate": 0.0
            }
        
        total_requests = len(items)
        total_tokens = sum(item.get('total_tokens', 0) for item in items)
        total_cost = sum(item.get('total_cost', 0.0) for item in items)
        successful_requests = sum(1 for item in items if item.get('success', True))
        
        # Aggregate by service
        by_service = {}
        for item in items:
            service = item.get('service_type', 'unknown')
            if service not in by_service:
                by_service[service] = {"requests": 0, "tokens": 0, "cost": 0.0}
            by_service[service]["requests"] += 1
            by_service[service]["tokens"] += item.get('total_tokens', 0)
            by_service[service]["cost"] += item.get('total_cost', 0.0)
        
        # Aggregate by model
        by_model = {}
        for item in items:
            model = item.get('model_name') or item.get('deployment_name', 'unknown')
            if model not in by_model:
                by_model[model] = {"requests": 0, "tokens": 0, "cost": 0.0}
            by_model[model]["requests"] += 1
            by_model[model]["tokens"] += item.get('total_tokens', 0)
            by_model[model]["cost"] += item.get('total_cost', 0.0)
        
        # Aggregate by date
        by_date = {}
        for item in items:
            timestamp = item.get('timestamp', '')
            if isinstance(timestamp, datetime):
                date_key = timestamp.strftime('%Y-%m-%d')
            else:
                date_key = str(timestamp)[:10] if timestamp else 'unknown'
            if date_key not in by_date:
                by_date[date_key] = {"requests": 0, "tokens": 0, "cost": 0.0}
            by_date[date_key]["requests"] += 1
            by_date[date_key]["tokens"] += item.get('total_tokens', 0)
            by_date[date_key]["cost"] += item.get('total_cost', 0.0)
        
        return {
            "total_requests": total_requests,
            "total_tokens": total_tokens,
            "total_cost": round(total_cost, 4),
            "by_service": by_service,
            "by_model": by_model,
            "by_date": by_date,
            "average_tokens_per_request": round(total_tokens / total_requests, 2) if total_requests > 0 else 0,
            "success_rate": round((successful_requests / total_requests) * 100, 2) if total_requests > 0 else 0.0
        }
    
    def get_usage_analytics(self, 
                           days_back: int = 7,
                           service_type: Optional[ServiceType] = None,
                           deployment_name: Optional[str] = None) -> Dict[str, Any]:
        """Get comprehensive usage analytics for the specified period"""
        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=days_back)
        
        return self.get_token_usage_analytics(
            start_date=start_date,
            end_date=end_date,
            service_type=service_type,
            model_name=deployment_name
        )
    
    def get_session_analytics(self, session_id: str) -> Dict[str, Any]:
        """Get analytics for a specific session"""
        session_records = [r for r in self._stored_records if r.session_id == session_id]
        items = [asdict(record) for record in session_records]
        return self._aggregate_token_usage(items)
    
    def get_recent_requests(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent token usage requests"""
        records_with_timestamp = [r for r in self._stored_records if r.timestamp is not None]
        recent_records = sorted(records_with_timestamp, key=lambda x: x.timestamp or datetime.min.replace(tzinfo=timezone.utc), reverse=True)[:limit]
        return [asdict(record) for record in recent_records]

token_tracker = TokenUsageTracker()
