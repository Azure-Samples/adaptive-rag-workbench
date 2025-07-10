const API_BASE_URL = import.meta.env.MODE === 'production' 
  ? '/api/v1' 
  : 'http://localhost:8002/api/v1';

export interface DocumentUploadRequest {
  files: File[];
  embedding_model?: string;
  search_type?: string;
  temperature?: number;
  document_type?: string;
  company_name?: string;
  filing_date?: string;
}

export interface DocumentUploadResponse {
  document_id: string;
  status: 'pending' | 'processing' | 'completed' | 'failed';
  message: string;
  processing_started_at: string;
}

export interface DocumentInfo {
  id: string;
  filename: string;
  type: string;
  size: number;
  uploadDate: string;
  status: string;
  chunks?: number;
  conflicts?: number;
  processingProgress?: number;
}

export interface ConflictInfo {
  id: string;
  documentId: string;
  chunkId: string;
  conflictType: string;
  description: string;
  sources: string[];
  status: string;
}

export interface KnowledgeBaseMetrics {
  total_documents: number;
  total_chunks: number;
  active_conflicts: number;
  processing_rate: number;
  documents_by_type: Record<string, number>;
  processing_queue_size: number;
  last_updated: string;
}

export interface AvailableEvaluatorsResponse {
  available_evaluators: {
    foundry: {
      available: boolean;
      metrics: string[];
    };
    custom: {
      available: boolean;
      metrics: string[];
    };
  };
  evaluator_types: string[];
  evaluation_metrics: string[];
  evaluation_models: string[];
}

class ApiService {
  private async makeRequest<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<T> {
    const url = `${API_BASE_URL}${endpoint}`;
    
    const response = await fetch(url, {
      headers: {
        'Content-Type': 'application/json',
        ...options.headers,
      },
      ...options,
    });

    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(`API Error: ${response.status} - ${errorText}`);
    }

    return response.json();
  }

  async uploadDocuments(request: DocumentUploadRequest): Promise<DocumentUploadResponse[]> {
    const formData = new FormData();
    
    request.files.forEach(file => {
      formData.append('files', file);
    });
    
    if (request.embedding_model) {
      formData.append('embedding_model', request.embedding_model);
    }
    if (request.search_type) {
      formData.append('search_type', request.search_type);
    }
    if (request.temperature !== undefined) {
      formData.append('temperature', request.temperature.toString());
    }
    if (request.document_type) {
      formData.append('document_type', request.document_type);
    }
    if (request.company_name) {
      formData.append('company_name', request.company_name);
    }
    if (request.filing_date) {
      formData.append('filing_date', request.filing_date);
    }

    const response = await fetch(`${API_BASE_URL}/documents/upload`, {
      method: 'POST',
      body: formData,
    });

    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(`Upload failed: ${response.status} - ${errorText}`);
    }

    return response.json();
  }

  async listDocuments(params?: {
    document_type?: string;
    company_name?: string;
    status?: string;
    limit?: number;
    offset?: number;
  }): Promise<{ documents: DocumentInfo[] }> {
    const searchParams = new URLSearchParams();
    
    if (params?.document_type) searchParams.append('document_type', params.document_type);
    if (params?.company_name) searchParams.append('company_name', params.company_name);
    if (params?.status) searchParams.append('status', params.status);
    if (params?.limit) searchParams.append('limit', params.limit.toString());
    if (params?.offset) searchParams.append('offset', params.offset.toString());

    const queryString = searchParams.toString();
    const endpoint = queryString ? `/knowledge-base/documents?${queryString}` : '/knowledge-base/documents';
    
    return this.makeRequest<{ documents: DocumentInfo[] }>(endpoint);
  }

  async getDocument(documentId: string): Promise<DocumentInfo> {
    return this.makeRequest<DocumentInfo>(`/documents/${documentId}`);
  }

  async deleteDocument(documentId: string): Promise<{ message: string }> {
    return this.makeRequest<{ message: string }>(`/documents/${documentId}`, {
      method: 'DELETE',
    });
  }

  async reprocessDocument(documentId: string): Promise<{ message: string }> {
    return this.makeRequest<{ message: string }>(`/documents/${documentId}/reprocess`, {
      method: 'POST',
    });
  }

  async getConflicts(params?: {
    status?: string;
    document_id?: string;
    limit?: number;
    offset?: number;
  }): Promise<{ conflicts: ConflictInfo[] }> {
    const searchParams = new URLSearchParams();
    
    if (params?.status) searchParams.append('status', params.status);
    if (params?.document_id) searchParams.append('document_id', params.document_id);
    if (params?.limit) searchParams.append('limit', params.limit.toString());
    if (params?.offset) searchParams.append('offset', params.offset.toString());

    const queryString = searchParams.toString();
    const endpoint = queryString ? `/knowledge-base/conflicts?${queryString}` : '/knowledge-base/conflicts';
    
    return this.makeRequest<{ conflicts: ConflictInfo[] }>(endpoint);
  }

  async resolveConflict(conflictId: string, status: 'resolved' | 'ignored'): Promise<{ message: string }> {
    return this.makeRequest<{ message: string }>(`/knowledge-base/conflicts/${conflictId}`, {
      method: 'PATCH',
      body: JSON.stringify({ status }),
    });
  }

  async getKnowledgeBaseMetrics(): Promise<KnowledgeBaseMetrics> {
    return this.makeRequest<KnowledgeBaseMetrics>('/knowledge-base/metrics');
  }

  async getDocumentContent(documentId: string, section?: string): Promise<{
    document_id: string;
    section?: string;
    content: string;
    chunks: any[];
    metadata: Record<string, any>;
  }> {
    const endpoint = section 
      ? `/documents/${documentId}/content?section=${encodeURIComponent(section)}`
      : `/documents/${documentId}/content`;
    
    return this.makeRequest(endpoint);
  }

  async getDocumentChunks(documentId: string, params?: {
    limit?: number;
    offset?: number;
    section?: string;
  }): Promise<{
    document_id: string;
    total_chunks: number;
    chunks: any[];
    section_filter?: string;
  }> {
    const searchParams = new URLSearchParams();
    
    if (params?.limit) searchParams.append('limit', params.limit.toString());
    if (params?.offset) searchParams.append('offset', params.offset.toString());
    if (params?.section) searchParams.append('section', params.section);

    const queryString = searchParams.toString();
    const endpoint = queryString 
      ? `/documents/${documentId}/chunks?${queryString}` 
      : `/documents/${documentId}/chunks`;
    
    return this.makeRequest(endpoint);
  }  async askQuestion(request: {
    question: string;
    session_id: string;
    verification_level: 'basic' | 'thorough' | 'comprehensive';
    chat_model?: string;
    embedding_model?: string;
    temperature?: number;
    credibility_check_enabled?: boolean;
    rag_method?: 'agent' | 'traditional' | 'llamaindex' | 'agentic-vector' | 'mcp';
    evaluation_enabled?: boolean;
    evaluator_type?: 'foundry' | 'custom';
    evaluation_model?: string;
  }): Promise<{
    answer: string;
    session_id: string;
    question_id: string;
    confidence_score: number;
    citations: any[];
    sub_questions: string[];
    verification_details: any;
    performance_benchmark?: any;
    reasoning_chain?: any;
    metadata: any;
    token_usage: any;
  }> {
    return this.makeRequest('/qa/ask', {
      method: 'POST',
      body: JSON.stringify(request),
    });
  }

  async decomposeQuestion(request: {
    question: string;
    session_id: string;
  }): Promise<{
    sub_questions: string[];
    session_id: string;
    metadata: any;
  }> {
    return this.makeRequest('/qa/decompose', {
      method: 'POST',
      body: JSON.stringify(request),
    });
  }

  async verifySource(request: {
    source_url: string;
    content: string;
    session_id: string;
  }): Promise<{
    credibility_score: number;
    verification_details: any;
    session_id: string;
    metadata: any;
  }> {
    return this.makeRequest('/qa/verify-sources', {
      method: 'POST',
      body: JSON.stringify(request),
    });
  }

  async getQACapabilities(): Promise<{
    available_models: string[];
    verification_levels: string[];
    supported_features: string[];
    agent_status: any;
  }> {
    return this.makeRequest('/qa/capabilities');
  }

  async getPerformanceMetrics(sessionId: string): Promise<{
    total_questions: number;
    average_efficiency_gain: number;
    average_accuracy_score: number;
    average_processing_time: number;
    complexity_breakdown: { [key: number]: number };
    time_saved_minutes: number;
    session_id: string;
    timestamp: string;
  }> {
    return this.makeRequest(`/qa/performance-metrics/${sessionId}`);
  }

  async getReasoningChain(questionId: string): Promise<{
    question_id: string;
    question: string;
    reasoning_steps: Array<{
      step_number: number;
      description: string;
      action_type: string;
      sources_consulted: string[];
      confidence: number;
      duration_ms: number;
      output: string;
      metadata: { [key: string]: any };
    }>;
    total_duration_ms: number;
    final_confidence: number;
    session_id: string;
    timestamp: string;
  }> {
    return this.makeRequest(`/qa/reasoning-chain/${questionId}`);
  }

  // Admin API methods
  async getTokenUsageRequests(params: {
    days?: number;
    service_type?: string;
    deployment_name?: string;
    limit?: number;
    offset?: number;
  } = {}): Promise<{
    requests: Array<{
      record_id: string;
      timestamp: string;
      session_id: string;
      service_type: string;
      operation_type: string;
      model_name: string;
      deployment_name: string;
      request_text: string;
      response_text: string;
      prompt_tokens: number;
      completion_tokens: number;
      total_tokens: number;
      total_cost: number;
      duration_ms: number;
      success: boolean;
      verification_level?: string;
      credibility_check_enabled: boolean;
      temperature?: number;
      max_tokens?: number;
      error_message?: string;
    }>;
    period_days: number;
    filters: any;
    pagination: any;
    timestamp: string;
  }> {
    const queryParams = new URLSearchParams();
    if (params.days) queryParams.append('days', params.days.toString());
    if (params.service_type) queryParams.append('service_type', params.service_type);    if (params.deployment_name) queryParams.append('deployment_name', params.deployment_name);
    if (params.limit) queryParams.append('limit', params.limit.toString());
    if (params.offset) queryParams.append('offset', params.offset.toString());
    
    return this.makeRequest(`/admin/token-usage/requests?${queryParams.toString()}`);
  }
  // SEC Documents batch processing methods
  async processMultipleSECDocuments(request: {
    filings: Array<{
      ticker: string;
      accession_number: string;
      document_id?: string;
    }>;
    batch_id?: string;
    max_parallel?: number;
  }): Promise<{
    batch_id: string;
    results: any[];
    summary: any;
    processing_time_seconds: number;
    total_chunks_created: number;
    total_tokens_used: number;
  }> {
    return this.makeRequest('/sec/documents/process-multiple', {
      method: 'POST',
      body: JSON.stringify(request),
    });
  }
  async getBatchStatus(batchId: string): Promise<{
    batch_id: string;
    total_documents: number;
    completed_documents: number;
    failed_documents: number;
    current_processing: Array<{
      document_id: string;
      ticker: string;
      accession_number: string;
      stage: string;
      progress_percent: number;
      message: string;
      started_at: string;
      updated_at: string;
      completed_at?: string;
      error_message?: string;
      chunks_created: number;
      tokens_used: number;
    }>;
    overall_progress_percent: number;
    started_at: string;
    finished_at?: string;
    estimated_completion?: string;
    status: string; // "processing", "completed", "failed"
    error_message?: string;
  }> {
    return this.makeRequest(`/sec/batch/${batchId}/status`);
  }

  async deleteSECDocument(documentId: string): Promise<{
    message: string;
    document_id: string;
    chunks_deleted: number;
    total_chunks_found: number;
  }> {
    return this.makeRequest(`/sec/documents/${documentId}`, {
      method: 'DELETE'
    });
  }

  async getQuestionPerformanceMetrics(questionId: string): Promise<any> {
    return this.makeRequest(`/qa/performance-metrics/question/${questionId}`);
  }

  // Evaluation endpoints
  async getEvaluationResult(evaluationId: string): Promise<{
    id: string;
    question_id: string;
    session_id: string;
    evaluator_type: string;
    rag_method: string;
    groundedness_score?: number;
    relevance_score?: number;
    coherence_score?: number;
    fluency_score?: number;
    similarity_score?: number;
    f1_score?: number;
    bleu_score?: number;
    rouge_score?: number;
    overall_score?: number;
    evaluation_model: string;
    evaluation_timestamp: string;
    evaluation_duration_ms?: number;
    question: string;
    answer: string;
    context: string[];
    ground_truth?: string;
    detailed_scores: any;
    reasoning?: string;
    feedback?: string;
    recommendations: string[];
    error?: string;
  }> {
    return this.makeRequest(`/evaluation/result/${evaluationId}`, {
      method: 'GET',
    });
  }

  async getEvaluationSummary(params: {
    session_id?: string;
    question_id?: string;
    rag_method?: string;
    evaluator_type?: string;
    start_date?: string;
    end_date?: string;
  }): Promise<{
    total_evaluations: number;
    avg_overall_score: number;
    avg_groundedness_score: number;
    avg_relevance_score: number;
    avg_coherence_score: number;
    avg_fluency_score: number;
    evaluations_by_rag_method: any;
    evaluations_by_evaluator_type: any;
    recent_evaluations: any[];
  }> {
    const queryParams = new URLSearchParams();
    Object.entries(params).forEach(([key, value]) => {
      if (value) queryParams.append(key, value);
    });
    
    return this.makeRequest(`/evaluation/summary?${queryParams.toString()}`, {
      method: 'GET',
    });
  }

  // Evaluation API methods
  async getEvaluationAnalytics(params: {
    days?: number;
    evaluator_type?: string;
    rag_method?: string;
  } = {}): Promise<any> {
    const searchParams = new URLSearchParams();
    if (params.days) searchParams.append('days', params.days.toString());
    if (params.evaluator_type && params.evaluator_type !== 'all') {
      searchParams.append('evaluator_type', params.evaluator_type);
    }
    if (params.rag_method && params.rag_method !== 'all') {
      searchParams.append('rag_method', params.rag_method);
    }
    
    return this.makeRequest(`/evaluation/analytics?${searchParams.toString()}`);
  }

  async getSessionEvaluationSummary(sessionId: string, params: {
    evaluator_type?: string;
    rag_method?: string;
  } = {}): Promise<any> {
    const searchParams = new URLSearchParams();
    if (params.evaluator_type && params.evaluator_type !== 'all') {
      searchParams.append('evaluator_type', params.evaluator_type);
    }
    if (params.rag_method && params.rag_method !== 'all') {
      searchParams.append('rag_method', params.rag_method);
    }
    
    return this.makeRequest(`/evaluation/summary/session/${sessionId}?${searchParams.toString()}`);
  }

  async getEvaluationResultsByQuestion(questionId: string): Promise<any[]> {
    return this.makeRequest(`/evaluation/results/question/${questionId}`);
  }

  async getEvaluationResultsBySession(sessionId: string, params: {
    evaluator_type?: string;
    rag_method?: string;
    limit?: number;
  } = {}): Promise<any[]> {
    const searchParams = new URLSearchParams();
    if (params.evaluator_type && params.evaluator_type !== 'all') {
      searchParams.append('evaluator_type', params.evaluator_type);
    }
    if (params.rag_method && params.rag_method !== 'all') {
      searchParams.append('rag_method', params.rag_method);
    }
    if (params.limit) {
      searchParams.append('limit', params.limit.toString());
    }
    
    return this.makeRequest(`/evaluation/results/session/${sessionId}?${searchParams.toString()}`);
  }

  async getAvailableEvaluators(): Promise<AvailableEvaluatorsResponse> {
    return this.makeRequest('/evaluation/evaluators');
  }

  async evaluateAnswer(request: {
    question_id: string;
    session_id: string;
    evaluator_type: string;
    rag_method: string;
    question: string;
    answer: string;
    context: string[];
    evaluation_model?: string;
    ground_truth?: string;
  }): Promise<any> {
    return this.makeRequest('/evaluation/evaluate', {
      method: 'POST',
      body: JSON.stringify(request),
    });
  }

  async deleteEvaluationResults(sessionId: string): Promise<any> {
    return this.makeRequest(`/evaluation/results/session/${sessionId}`, {
      method: 'DELETE',
    });
  }
}

export const apiService = new ApiService();
