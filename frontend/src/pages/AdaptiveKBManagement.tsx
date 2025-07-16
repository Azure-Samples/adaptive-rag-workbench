import React, { useState, useRef } from 'react';
import { ChatLayout } from '../components/ChatLayout';
import { Button } from '../components/ui/button';
import { Card } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { CompanySearch } from '../components/CompanySearch';
import { DocumentUpload } from '../components/DocumentUpload';
import { Upload, FileText, RefreshCw, Database, TrendingUp, Building2, Search, CheckCircle, AlertCircle, Clock, Zap, Settings, Trash2, ShieldAlert } from 'lucide-react';
import { useTheme } from '../contexts/ThemeContext';

interface ProcessingStep {
  id: string;
  title: string;
  description: string;
  status: 'pending' | 'processing' | 'completed' | 'error';
  progress?: number;
  message?: string;
}

interface ProcessingResult {
  chunks_created: number;
  company: string;
  document_type: string;
  processing_time: number;
  credibility_score: number;
  metadata: any;
}

export function AdaptiveKBManagement() {
  const { theme } = useTheme();
  
  const [uploadStatus, setUploadStatus] = useState<string>('');
  const [isUploading, setIsUploading] = useState(false);
  const [indexStats, setIndexStats] = useState<{
    total_documents?: number;
    company_breakdown?: Record<string, number>;
    [key: string]: unknown;
  } | null>(null);
  const [activeTab, setActiveTab] = useState<'upload' | 'search' | 'admin'>('upload');
  const [processingSteps, setProcessingSteps] = useState<ProcessingStep[]>([]);
  const [processingResult, setProcessingResult] = useState<ProcessingResult | null>(null);
  const [, setCurrentSessionId] = useState<string | null>(null);
  const [useProgressTracking, setUseProgressTracking] = useState(true);
  const [adminOperationStatus, setAdminOperationStatus] = useState<string>('');
  const [isAdminOperationInProgress, setIsAdminOperationInProgress] = useState(false);
  const [azureServiceStatus, setAzureServiceStatus] = useState<any>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const initializeProcessingSteps = () => {
    return [
      {
        id: 'validation',
        title: 'File Validation',
        description: 'Validating file format and size',
        status: 'pending',
      },
      {
        id: 'extraction',
        title: 'Content Extraction',
        description: 'Extracting content using Azure Document Intelligence',
        status: 'pending',
      },
      {
        id: 'metadata',
        title: 'Metadata Analysis',
        description: 'Analyzing document metadata and structure',
        status: 'pending',
      },
      {
        id: 'assessment',
        title: 'Credibility Assessment',
        description: 'Evaluating document credibility and quality',
        status: 'pending',
      },
      {
        id: 'chunking',
        title: 'Intelligent Chunking',
        description: 'Creating structure-aware content chunks',
        status: 'pending',
      },
      {
        id: 'embeddings',
        title: 'Vector Embeddings',
        description: 'Generating semantic embeddings',
        status: 'pending',
      },
      {
        id: 'indexing',
        title: 'Search Indexing',
        description: 'Indexing content in Azure Search',
        status: 'pending',
      },
    ] as ProcessingStep[];
  };

  const updateProcessingStep = (stepId: string, status: ProcessingStep['status'], progress?: number, message?: string) => {
    setProcessingSteps(prevSteps => 
      prevSteps.map(step => 
        step.id === stepId 
          ? { ...step, status, progress, message }
          : step
      )
    );
  };

  const handleFileUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    setIsUploading(true);
    setProcessingResult(null);
    setUploadStatus('');

    if (useProgressTracking) {
      // Use progress tracking with SSE
      await handleFileUploadWithProgress(file);
    } else {
      // Use simple upload
      await handleSimpleFileUpload(file);
    }
  };

  const handleSimpleFileUpload = async (file: File) => {
    setUploadStatus('Uploading file...');

    try {
      const formData = new FormData();
      formData.append('file', file);

      const response = await fetch('/api/upload', {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        throw new Error(`Upload failed: ${response.statusText}`);
      }

      const result = await response.json();
      setUploadStatus(`Success: ${result.message}`);
      setProcessingResult(result);

      fetchIndexStats();
    } catch (error) {
      setUploadStatus(`Error: ${error instanceof Error ? error.message : 'Unknown error'}`);
    } finally {
      setIsUploading(false);
    }
  };

  const handleFileUploadWithProgress = async (file: File) => {
    const sessionId = `session_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    setCurrentSessionId(sessionId);
    setProcessingSteps(initializeProcessingSteps());

    try {
      // Start upload with progress tracking
      const formData = new FormData();
      formData.append('file', file);

      const uploadResponse = await fetch(`/api/upload-with-progress/${sessionId}`, {
        method: 'POST',
        body: formData,
      });

      if (!uploadResponse.ok) {
        throw new Error(`Upload failed: ${uploadResponse.statusText}`);
      }

      // Start listening to progress stream
      const eventSource = new EventSource(`/api/processing-stream/${sessionId}`);

      eventSource.onopen = (event) => {
        console.log('SSE connection opened successfully:', event);
        setUploadStatus('Connected to processing stream...');
      };

      eventSource.onmessage = (event) => {
        try {
          console.log('SSE message received:', event.data);
          const data = JSON.parse(event.data);
          
          if (data.type === 'connected') {
            console.log(`Connected to processing stream for session: ${data.session_id}`);
            setUploadStatus('Connected - processing will begin shortly...');
          } else if (data.type === 'progress') {
            const stepMapping: Record<string, string> = {
              'VALIDATION': 'validation',
              'EXTRACTION': 'extraction',
              'METADATA': 'metadata',
              'ASSESSMENT': 'assessment',
              'CHUNKING': 'chunking',
              'EMBEDDINGS': 'embeddings',
              'INDEXING': 'indexing'
            };

            const stepId = stepMapping[data.step] || data.step.toLowerCase();
            updateProcessingStep(stepId, 'processing', data.progress, data.message);
            
            setUploadStatus(`${data.step}: ${data.message}`);
          } else if (data.type === 'status') {
            if (data.status === 'completed') {
              // Mark all steps as completed
              setProcessingSteps(prevSteps => 
                prevSteps.map(step => ({ ...step, status: 'completed' }))
              );
              
              setUploadStatus(`Processing completed in ${data.result?.processing_time || 0}s`);
              setProcessingResult(data.result || null);
              fetchIndexStats();
              eventSource.close();
              setIsUploading(false);
              // Reset file input
              if (fileInputRef.current) {
                fileInputRef.current.value = '';
              }
            } else if (data.status === 'error') {
              setUploadStatus(`Error: ${data.error}`);
              setProcessingSteps(prevSteps => 
                prevSteps.map(step => 
                  step.status === 'processing' 
                    ? { ...step, status: 'error' }
                    : step
                )
              );
              eventSource.close();
              setIsUploading(false);
              // Reset file input
              if (fileInputRef.current) {
                fileInputRef.current.value = '';
              }
            } else {
              // Update current status
              if (data.current_message) {
                setUploadStatus(`${data.step || 'Processing'}: ${data.current_message}`);
              }
            }
          } else if (data.type === 'timeout') {
            setUploadStatus(`Processing timeout: ${data.message}`);
            setProcessingSteps(prevSteps => 
              prevSteps.map(step => 
                step.status === 'processing' 
                  ? { ...step, status: 'error', message: 'Timeout' }
                  : step
              )
            );
            eventSource.close();
            setIsUploading(false);
            // Reset file input
            if (fileInputRef.current) {
              fileInputRef.current.value = '';
            }
          } else if (data.type === 'error') {
            setUploadStatus(`Stream error: ${data.message}`);
            setProcessingSteps(prevSteps => 
              prevSteps.map(step => 
                step.status === 'processing' 
                  ? { ...step, status: 'error' }
                  : step
              )
            );
            eventSource.close();
            setIsUploading(false);
            // Reset file input
            if (fileInputRef.current) {
              fileInputRef.current.value = '';
            }
          }
        } catch (parseError) {
          console.error('Error parsing SSE data:', parseError, 'Raw data:', event.data);
          setUploadStatus('Error parsing server response');
        }
      };

      eventSource.onerror = (error) => {
        console.error('SSE error occurred:', error);
        console.log('EventSource readyState:', eventSource.readyState);
        console.log('EventSource URL:', eventSource.url);
        
        // Check if it's a connection error vs other error
        if (eventSource.readyState === EventSource.CONNECTING) {
          setUploadStatus('Retrying connection to processing stream...');
          // Don't close immediately, let it retry
          return;
        } else if (eventSource.readyState === EventSource.CLOSED) {
          setUploadStatus('Connection closed by server - check backend logs');
        } else {
          setUploadStatus('Connection error during processing - check network/backend');
        }
        
        eventSource.close();
        setIsUploading(false);
        // Reset file input
        if (fileInputRef.current) {
          fileInputRef.current.value = '';
        }
      };

      // Clean up after 10 minutes (extended for document processing)
              setTimeout(() => {
          if (eventSource.readyState !== EventSource.CLOSED) {
            console.log('Closing SSE connection due to timeout');
            eventSource.close();
            setIsUploading(false);
            setUploadStatus('Processing timeout - connection closed');
            // Reset file input
            if (fileInputRef.current) {
              fileInputRef.current.value = '';
            }
          }
        }, 600000);

    } catch (error) {
      setUploadStatus(`Error: ${error instanceof Error ? error.message : 'Unknown error'}`);
      setIsUploading(false);
    }
  };

  const fetchIndexStats = async () => {
    try {
      const response = await fetch('/api/index-stats');
      const stats = await response.json();
      setIndexStats(stats);
    } catch (error) {
      console.error('Failed to fetch index stats:', error);
    }
  };

  const fetchAzureServiceStatus = async () => {
    try {
      const response = await fetch('/api/azure-service-status');
      const status = await response.json();
      setAzureServiceStatus(status);
    } catch (error) {
      console.error('Failed to fetch Azure service status:', error);
    }
  };

  const recreateSearchIndex = async () => {
    if (!window.confirm('WARNING: This will DELETE ALL existing data in the search index. Are you sure you want to continue?')) {
      return;
    }

    setIsAdminOperationInProgress(true);
    setAdminOperationStatus('Recreating search index...');

    try {
      const response = await fetch('/api/recreate-index', { method: 'POST' });
      const result = await response.json();
      
      if (result.status === 'success') {
        setAdminOperationStatus(`Success: ${result.message}`);
        // Refresh stats after recreation
        await fetchIndexStats();
        await fetchAzureServiceStatus();
      } else {
        setAdminOperationStatus(`Error: ${result.message}`);
      }
    } catch (error) {
      setAdminOperationStatus(`Error: ${error instanceof Error ? error.message : 'Unknown error'}`);
    } finally {
      setIsAdminOperationInProgress(false);
    }
  };

  const ensureSearchIndex = async () => {
    setIsAdminOperationInProgress(true);
    setAdminOperationStatus('Ensuring search index exists...');

    try {
      const response = await fetch('/api/ensure-index', { method: 'POST' });
      const result = await response.json();
      
      if (result.status === 'success') {
        setAdminOperationStatus(`Success: ${result.message}`);
        await fetchIndexStats();
        await fetchAzureServiceStatus();
      } else {
        setAdminOperationStatus(`Error: ${result.message}`);
      }
    } catch (error) {
      setAdminOperationStatus(`Error: ${error instanceof Error ? error.message : 'Unknown error'}`);
    } finally {
      setIsAdminOperationInProgress(false);
    }
  };

  React.useEffect(() => {
    fetchIndexStats();
    fetchAzureServiceStatus();
  }, []);

  return (
    <ChatLayout>
      <div className={`flex-1 overflow-y-auto p-6 ${
        theme === 'dark' 
          ? 'bg-gray-900' 
          : theme === 'customer' 
            ? 'bg-customer-50' 
            : 'bg-gray-50'
      }`} style={{ height: 'calc(100vh - 200px)' }}>
        <div className="max-w-6xl mx-auto space-y-8">
          {/* Tab Navigation */}
          <div className={`flex space-x-1 p-1 rounded-lg w-fit ${
            theme === 'dark' 
              ? 'bg-gray-800' 
              : theme === 'customer' 
                ? 'bg-customer-100' 
                : 'bg-gray-100'
          }`}>
            <button
              onClick={() => setActiveTab('upload')}
              className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
                activeTab === 'upload'
                  ? theme === 'dark' 
                    ? 'bg-gray-700 text-white shadow-sm' 
                    : theme === 'customer' 
                      ? 'bg-customer-500 text-white shadow-sm' 
                      : 'bg-white text-microsoft-gray shadow-sm'
                  : theme === 'dark' 
                    ? 'text-gray-300 hover:text-white' 
                    : theme === 'customer' 
                      ? 'text-customer-600 hover:text-customer-800' 
                      : 'text-gray-600 hover:text-microsoft-gray'
              }`}
            >
              <Upload className="h-4 w-4 mr-2 inline" />
              Upload Documents
            </button>
            <button
              onClick={() => setActiveTab('search')}
              className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
                activeTab === 'search'
                  ? theme === 'dark' 
                    ? 'bg-gray-700 text-white shadow-sm' 
                    : theme === 'customer' 
                      ? 'bg-customer-500 text-white shadow-sm' 
                      : 'bg-white text-microsoft-gray shadow-sm'
                  : theme === 'dark' 
                    ? 'text-gray-300 hover:text-white' 
                    : theme === 'customer' 
                      ? 'text-customer-600 hover:text-customer-800' 
                      : 'text-gray-600 hover:text-microsoft-gray'
              }`}
            >
              <Search className="h-4 w-4 mr-2 inline" />
              Company Search
            </button>
            <button
              onClick={() => setActiveTab('admin')}
              className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
                activeTab === 'admin'
                  ? theme === 'dark' 
                    ? 'bg-gray-700 text-white shadow-sm' 
                    : theme === 'customer' 
                      ? 'bg-customer-500 text-white shadow-sm' 
                      : 'bg-white text-microsoft-gray shadow-sm'
                  : theme === 'dark' 
                    ? 'text-gray-300 hover:text-white' 
                    : theme === 'customer' 
                      ? 'text-customer-600 hover:text-customer-800' 
                      : 'text-gray-600 hover:text-microsoft-gray'
              }`}
            >
              <Settings className="h-4 w-4 mr-2 inline" />
              Admin
            </button>
          </div>
          
          {activeTab === 'upload' && (
            <>
              <Card className={`p-8 border shadow-xl ${
                  theme === 'dark' 
                    ? 'bg-gradient-to-br from-gray-800 to-gray-900 border-gray-700' 
                    : theme === 'customer' 
                      ? 'bg-gradient-to-br from-customer-50 to-customer-100 border-customer-200' 
                      : 'bg-gradient-to-br from-white to-gray-50 border-gray-200'
                }`}>
                <div className="flex items-center space-x-3 mb-6">
                  <div className={`w-10 h-10 rounded-full flex items-center justify-center ${
                    theme === 'dark' 
                      ? 'bg-gray-600' 
                      : theme === 'customer' 
                        ? 'bg-customer-500' 
                        : 'bg-microsoft-purple'
                  }`}>
                    <Upload className="h-5 w-5 text-white" />
                  </div>
                  <div>
                    <h3 className={`text-xl font-semibold ${
                      theme === 'dark' 
                        ? 'text-white' 
                        : theme === 'customer' 
                          ? 'text-customer-900' 
                          : 'text-microsoft-gray'
                    }`}>Upload New Documents</h3>
                    <p className={`${
                      theme === 'dark' 
                        ? 'text-gray-300' 
                        : theme === 'customer' 
                          ? 'text-customer-700' 
                          : 'text-gray-600'
                    }`}>Upload new 10-K filings or other financial documents to automatically update the knowledge base.</p>
                  </div>
                </div>

            <DocumentUpload />

            {/* Progress Tracking Toggle */}
            <div className="mt-4 flex items-center space-x-3">
              <label className="flex items-center space-x-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={useProgressTracking}
                  onChange={(e) => setUseProgressTracking(e.target.checked)}
                  className={`rounded focus:ring-2 ${
                    theme === 'dark' 
                      ? 'border-gray-600 bg-gray-700 text-gray-500 focus:ring-gray-500' 
                      : theme === 'customer' 
                        ? 'border-customer-300 text-customer-500 focus:ring-customer-500' 
                        : 'border-gray-300 text-microsoft-purple focus:ring-microsoft-purple'
                  }`}
                />
                <span className={`text-sm ${
                  theme === 'dark' 
                    ? 'text-gray-300' 
                    : theme === 'customer' 
                      ? 'text-customer-700' 
                      : 'text-gray-600'
                }`}>Enable real-time progress tracking</span>
              </label>
            </div>

            {/* Debug Tools */}
            {process.env.NODE_ENV === 'development' && (
              <div className={`mt-4 p-4 rounded-lg border ${
                theme === 'dark' 
                  ? 'bg-gray-800 border-gray-700' 
                  : theme === 'customer' 
                    ? 'bg-customer-50 border-customer-200' 
                    : 'bg-gray-50 border-gray-200'
              }`}>
                <h4 className={`text-sm font-medium mb-2 ${
                  theme === 'dark' 
                    ? 'text-gray-200' 
                    : theme === 'customer' 
                      ? 'text-customer-800' 
                      : 'text-gray-700'
                }`}>Debug Tools</h4>
                <div className="flex space-x-2">
                  <Button
                    onClick={async () => {
                      try {
                        const response = await fetch('/api/recreate-index', { method: 'POST' });
                        const result = await response.json();
                        alert(`Index recreation: ${result.status} - ${result.message}`);
                      } catch (e) {
                        alert(`Error: ${e}`);
                      }
                    }}
                    variant="outline"
                    size="sm"
                  >
                    Recreate Search Index
                  </Button>
                  <Button
                    onClick={() => {
                      const testSessionId = `test_${Date.now()}`;
                      const eventSource = new EventSource(`/api/test-sse/${testSessionId}`);
                      let messageCount = 0;
                      
                      eventSource.onmessage = (event) => {
                        messageCount++;
                        console.log(`Test SSE message ${messageCount}:`, event.data);
                        if (messageCount >= 3) {
                          eventSource.close();
                          alert(`SSE test successful - received ${messageCount} messages`);
                        }
                      };
                      
                      eventSource.onerror = (error) => {
                        console.error('Test SSE error:', error);
                        eventSource.close();
                        alert('SSE test failed - check console');
                      };
                    }}
                    variant="outline"
                    size="sm"
                  >
                    Test SSE Connection
                  </Button>
                </div>
              </div>
            )}

            {/* Processing Steps Display */}
            {isUploading && useProgressTracking && processingSteps.length > 0 && (
              <div className="mt-6 space-y-4">
                <h4 className={`font-semibold flex items-center ${
                  theme === 'dark' 
                    ? 'text-white' 
                    : theme === 'customer' 
                      ? 'text-customer-900' 
                      : 'text-microsoft-gray'
                }`}>
                  <Clock className={`h-5 w-5 mr-2 ${
                    theme === 'dark' 
                      ? 'text-gray-400' 
                      : theme === 'customer' 
                        ? 'text-customer-500' 
                        : 'text-microsoft-blue'
                  }`} />
                  Processing Steps
                </h4>
                <div className="space-y-3">
                  {processingSteps.map((step) => (
                    <div key={step.id} className={`flex items-center space-x-3 p-3 rounded-lg ${
                      theme === 'dark' 
                        ? 'bg-gray-800' 
                        : theme === 'customer' 
                          ? 'bg-customer-50' 
                          : 'bg-gray-50'
                    }`}>
                      <div className="flex-shrink-0">
                        {step.status === 'completed' && (
                          <CheckCircle className="h-5 w-5 text-green-500" />
                        )}
                        {step.status === 'processing' && (
                          <RefreshCw className={`h-5 w-5 animate-spin ${
                            theme === 'dark' 
                              ? 'text-gray-400' 
                              : theme === 'customer' 
                                ? 'text-customer-500' 
                                : 'text-microsoft-blue'
                          }`} />
                        )}
                        {step.status === 'error' && (
                          <AlertCircle className="h-5 w-5 text-red-500" />
                        )}
                        {step.status === 'pending' && (
                          <div className={`h-5 w-5 rounded-full border-2 ${
                            theme === 'dark' 
                              ? 'border-gray-600' 
                              : theme === 'customer' 
                                ? 'border-customer-300' 
                                : 'border-gray-300'
                          }`} />
                        )}
                      </div>
                      <div className="flex-1">
                        <div className={`font-medium ${
                          theme === 'dark' 
                            ? 'text-white' 
                            : theme === 'customer' 
                              ? 'text-customer-900' 
                              : 'text-microsoft-gray'
                        }`}>{step.title}</div>
                        <div className={`text-sm ${
                          theme === 'dark' 
                            ? 'text-gray-300' 
                            : theme === 'customer' 
                              ? 'text-customer-700' 
                              : 'text-gray-600'
                        }`}>
                          {step.message || step.description}
                        </div>
                        {step.progress !== undefined && step.status === 'processing' && (
                          <div className={`mt-2 w-full rounded-full h-2 ${
                            theme === 'dark' 
                              ? 'bg-gray-700' 
                              : theme === 'customer' 
                                ? 'bg-customer-200' 
                                : 'bg-gray-200'
                          }`}>
                            <div 
                              className={`h-2 rounded-full transition-all duration-300 ${
                                theme === 'dark' 
                                  ? 'bg-gray-400' 
                                  : theme === 'customer' 
                                    ? 'bg-customer-500' 
                                    : 'bg-microsoft-blue'
                              }`}
                              style={{ width: `${step.progress}%` }}
                            />
                          </div>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Processing Results */}
            {processingResult && (
              <div className={`mt-6 p-6 rounded-lg border ${
                theme === 'dark' 
                  ? 'bg-gradient-to-r from-gray-800 to-gray-700 border-gray-600' 
                  : theme === 'customer' 
                    ? 'bg-gradient-to-r from-customer-50 to-customer-100 border-customer-300' 
                    : 'bg-gradient-to-r from-green-50 to-primary/10 border-green-200'
              }`}>
                <h4 className={`font-semibold mb-4 flex items-center ${
                  theme === 'dark' 
                    ? 'text-white' 
                    : theme === 'customer' 
                      ? 'text-customer-900' 
                      : 'text-microsoft-gray'
                }`}>
                  <Zap className={`h-5 w-5 mr-2 ${
                    theme === 'dark' 
                      ? 'text-gray-400' 
                      : theme === 'customer' 
                        ? 'text-customer-500' 
                        : 'text-microsoft-green'
                  }`} />
                  Processing Results
                </h4>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                  <div className={`p-4 rounded-lg border ${
                    theme === 'dark' 
                      ? 'bg-gray-700 border-gray-600' 
                      : theme === 'customer' 
                        ? 'bg-customer-100 border-customer-300' 
                        : 'bg-white border-gray-200'
                  }`}>
                    <div className={`text-2xl font-bold ${
                      theme === 'dark' 
                        ? 'text-gray-300' 
                        : theme === 'customer' 
                          ? 'text-customer-600' 
                          : 'text-microsoft-blue'
                    }`}>
                      {processingResult.chunks_created}
                    </div>
                    <div className={`text-sm font-medium ${
                      theme === 'dark' 
                        ? 'text-gray-400' 
                        : theme === 'customer' 
                          ? 'text-customer-700' 
                          : 'text-primary'
                    }`}>Chunks Created</div>
                  </div>
                  <div className={`p-4 rounded-lg border ${
                    theme === 'dark' 
                      ? 'bg-gray-700 border-gray-600' 
                      : theme === 'customer' 
                        ? 'bg-customer-100 border-customer-300' 
                        : 'bg-white border-gray-200'
                  }`}>
                    <div className={`text-2xl font-bold ${
                      theme === 'dark' 
                        ? 'text-gray-300' 
                        : theme === 'customer' 
                          ? 'text-customer-600' 
                          : 'text-microsoft-green'
                    }`}>
                      {processingResult.company}
                    </div>
                    <div className={`text-sm font-medium ${
                      theme === 'dark' 
                        ? 'text-gray-400' 
                        : theme === 'customer' 
                          ? 'text-customer-700' 
                          : 'text-green-700'
                    }`}>Company</div>
                  </div>
                  <div className={`p-4 rounded-lg border ${
                    theme === 'dark' 
                      ? 'bg-gray-700 border-gray-600' 
                      : theme === 'customer' 
                        ? 'bg-customer-100 border-customer-300' 
                        : 'bg-white border-gray-200'
                  }`}>
                    <div className={`text-2xl font-bold ${
                      theme === 'dark' 
                        ? 'text-gray-300' 
                        : theme === 'customer' 
                          ? 'text-customer-600' 
                          : 'text-microsoft-purple'
                    }`}>
                      {processingResult.processing_time.toFixed(1)}s
                    </div>
                    <div className={`text-sm font-medium ${
                      theme === 'dark' 
                        ? 'text-gray-400' 
                        : theme === 'customer' 
                          ? 'text-customer-700' 
                          : 'text-purple-700'
                    }`}>Processing Time</div>
                  </div>
                  <div className={`p-4 rounded-lg border ${
                    theme === 'dark' 
                      ? 'bg-gray-700 border-gray-600' 
                      : theme === 'customer' 
                        ? 'bg-customer-100 border-customer-300' 
                        : 'bg-white border-gray-200'
                  }`}>
                    <div className={`text-2xl font-bold ${
                      theme === 'dark' 
                        ? 'text-gray-300' 
                        : theme === 'customer' 
                          ? 'text-customer-600' 
                          : 'text-microsoft-orange'
                    }`}>
                      {(processingResult.credibility_score * 100).toFixed(0)}%
                    </div>
                    <div className={`text-sm font-medium ${
                      theme === 'dark' 
                        ? 'text-gray-400' 
                        : theme === 'customer' 
                          ? 'text-customer-700' 
                          : 'text-orange-700'
                    }`}>Credibility Score</div>
                  </div>
                </div>
                
                {processingResult.metadata && (
                  <div className={`mt-4 p-4 rounded-lg border ${
                    theme === 'dark' 
                      ? 'bg-gray-700 border-gray-600' 
                      : theme === 'customer' 
                        ? 'bg-customer-100 border-customer-300' 
                        : 'bg-white border-gray-200'
                  }`}>
                    <h5 className={`font-medium mb-2 ${
                      theme === 'dark' 
                        ? 'text-white' 
                        : theme === 'customer' 
                          ? 'text-customer-900' 
                          : 'text-microsoft-gray'
                    }`}>Document Metadata</h5>
                    <div className="grid grid-cols-2 md:grid-cols-3 gap-2 text-sm">
                      <div>
                        <span className={`${
                          theme === 'dark' 
                            ? 'text-gray-300' 
                            : theme === 'customer' 
                              ? 'text-customer-700' 
                              : 'text-gray-600'
                        }`}>Type:</span>
                        <span className={`ml-2 font-medium ${
                          theme === 'dark' 
                            ? 'text-gray-200' 
                            : theme === 'customer' 
                              ? 'text-customer-800' 
                              : 'text-gray-900'
                        }`}>{processingResult.document_type}</span>
                      </div>
                      <div>
                        <span className={`${
                          theme === 'dark' 
                            ? 'text-gray-300' 
                            : theme === 'customer' 
                              ? 'text-customer-700' 
                              : 'text-gray-600'
                        }`}>Content Length:</span>
                        <span className={`ml-2 font-medium ${
                          theme === 'dark' 
                            ? 'text-gray-200' 
                            : theme === 'customer' 
                              ? 'text-customer-800' 
                              : 'text-gray-900'
                        }`}>{processingResult.metadata.content_length?.toLocaleString()}</span>
                      </div>
                      <div>
                        <span className={`${
                          theme === 'dark' 
                            ? 'text-gray-300' 
                            : theme === 'customer' 
                              ? 'text-customer-700' 
                              : 'text-gray-600'
                        }`}>File Size:</span>
                        <span className={`ml-2 font-medium ${
                          theme === 'dark' 
                            ? 'text-gray-200' 
                            : theme === 'customer' 
                              ? 'text-customer-800' 
                              : 'text-gray-900'
                        }`}>{(processingResult.metadata.file_size / 1024).toFixed(1)}KB</span>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            )}

            {uploadStatus && !processingResult && (
              <div className={`mt-6 p-4 rounded-lg border ${
                uploadStatus.startsWith('Error')
                  ? 'bg-red-50 text-red-700 border-red-200'
                  : 'bg-green-50 text-green-700 border-green-200'
              }`}>
                <div className="flex items-center space-x-2">
                  {uploadStatus.startsWith('Error') ? (
                    <AlertCircle className="h-5 w-5 text-red-500" />
                  ) : (
                    <CheckCircle className="h-5 w-5 text-green-500" />
                  )}
                  <span className="font-medium">{uploadStatus}</span>
                </div>
              </div>
            )}
          </Card>

          <Card className={`p-8 border shadow-xl ${
              theme === 'dark' 
                ? 'bg-gradient-to-br from-gray-800 to-gray-900 border-gray-700' 
                : theme === 'customer' 
                  ? 'bg-gradient-to-br from-customer-50 to-customer-100 border-customer-200' 
                  : 'bg-gradient-to-br from-white to-gray-50 border-gray-200'
            }`}>
            <div className="flex items-center justify-between mb-6">
              <div className="flex items-center space-x-3">
                <div className={`w-10 h-10 rounded-full flex items-center justify-center ${
                  theme === 'dark' 
                    ? 'bg-gray-600' 
                    : theme === 'customer' 
                      ? 'bg-customer-500' 
                      : 'bg-microsoft-blue'
                }`}>
                  <Database className="h-5 w-5 text-white" />
                </div>
                <div>
                  <h3 className={`text-xl font-semibold ${
                    theme === 'dark' 
                      ? 'text-white' 
                      : theme === 'customer' 
                        ? 'text-customer-900' 
                        : 'text-microsoft-gray'
                  }`}>Knowledge Base Statistics</h3>
                  <p className={`${
                    theme === 'dark' 
                      ? 'text-gray-300' 
                      : theme === 'customer' 
                        ? 'text-customer-700' 
                        : 'text-gray-600'
                  }`}>Real-time insights into your document repository</p>
                </div>
              </div>
              <Button
                onClick={fetchIndexStats}
                variant="outline"
                size="sm"
                className={`${
                  theme === 'dark' 
                    ? 'border-gray-600 hover:bg-gray-700 text-gray-200' 
                    : theme === 'customer' 
                      ? 'border-customer-300 hover:bg-customer-50 text-customer-700' 
                      : 'border-gray-300 hover:bg-gray-50'
                }`}
              >
                <RefreshCw className="h-4 w-4 mr-2" />
                Refresh
              </Button>
            </div>

            {indexStats ? (
              <div className="space-y-6">
                <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                  <Card className={`p-6 ${
                    theme === 'dark' 
                      ? 'bg-gradient-to-br from-gray-700 to-gray-800 border-gray-600' 
                      : theme === 'customer' 
                        ? 'bg-gradient-to-br from-customer-50 to-customer-100 border-customer-200' 
                        : 'bg-gradient-to-br from-primary/10 to-primary/20 border-primary/30'
                  }`}>
                    <div className="flex items-center space-x-3">
                      <FileText className={`h-8 w-8 ${
                        theme === 'dark' 
                          ? 'text-gray-300' 
                          : theme === 'customer' 
                            ? 'text-customer-600' 
                            : 'text-microsoft-blue'
                      }`} />
                      <div>
                        <div className={`text-3xl font-bold ${
                          theme === 'dark' 
                            ? 'text-white' 
                            : theme === 'customer' 
                              ? 'text-customer-700' 
                              : 'text-microsoft-blue'
                        }`}>
                          {indexStats.total_documents?.toLocaleString() || 0}
                        </div>
                        <div className={`text-sm font-medium ${
                          theme === 'dark' 
                            ? 'text-gray-300' 
                            : theme === 'customer' 
                              ? 'text-customer-600' 
                              : 'text-primary'
                        }`}>Total Documents</div>
                      </div>
                    </div>
                  </Card>

                  <Card className={`p-6 ${
                    theme === 'dark' 
                      ? 'bg-gradient-to-br from-gray-700 to-gray-800 border-gray-600' 
                      : theme === 'customer' 
                        ? 'bg-gradient-to-br from-customer-100 to-customer-200 border-customer-300' 
                        : 'bg-gradient-to-br from-green-50 to-green-100 border-green-200'
                  }`}>
                    <div className="flex items-center space-x-3">
                      <Building2 className={`h-8 w-8 ${
                        theme === 'dark' 
                          ? 'text-gray-300' 
                          : theme === 'customer' 
                            ? 'text-customer-600' 
                            : 'text-microsoft-green'
                      }`} />
                      <div>
                        <div className={`text-3xl font-bold ${
                          theme === 'dark' 
                            ? 'text-white' 
                            : theme === 'customer' 
                              ? 'text-customer-700' 
                              : 'text-microsoft-green'
                        }`}>
                          {Object.keys(indexStats.company_breakdown || {}).length}
                        </div>
                        <div className={`text-sm font-medium ${
                          theme === 'dark' 
                            ? 'text-gray-300' 
                            : theme === 'customer' 
                              ? 'text-customer-600' 
                              : 'text-green-700'
                        }`}>Companies Indexed</div>
                      </div>
                    </div>
                  </Card>

                  <Card className={`p-6 ${
                    theme === 'dark' 
                      ? 'bg-gradient-to-br from-gray-700 to-gray-800 border-gray-600' 
                      : theme === 'customer' 
                        ? 'bg-gradient-to-br from-customer-200 to-customer-300 border-customer-400' 
                        : 'bg-gradient-to-br from-purple-50 to-purple-100 border-purple-200'
                  }`}>
                    <div className="flex items-center space-x-3">
                      <TrendingUp className={`h-8 w-8 ${
                        theme === 'dark' 
                          ? 'text-gray-300' 
                          : theme === 'customer' 
                            ? 'text-customer-600' 
                            : 'text-microsoft-purple'
                      }`} />
                      <div>
                        <div className={`text-3xl font-bold ${
                          theme === 'dark' 
                            ? 'text-white' 
                            : theme === 'customer' 
                              ? 'text-customer-700' 
                              : 'text-microsoft-purple'
                        }`}>
                          {Math.round((Number(indexStats.total_documents) || 0) / Math.max(Object.keys((indexStats.company_breakdown as Record<string, unknown>) || {}).length, 1))}
                        </div>
                        <div className={`text-sm font-medium ${
                          theme === 'dark' 
                            ? 'text-gray-300' 
                            : theme === 'customer' 
                              ? 'text-customer-600' 
                              : 'text-purple-700'
                        }`}>Avg Docs/Company</div>
                      </div>
                    </div>
                  </Card>
                </div>

                {indexStats.company_breakdown && typeof indexStats.company_breakdown === 'object' && (
                  <Card className={`p-8 border shadow-xl ${
                      theme === 'dark' 
                        ? 'bg-gradient-to-br from-gray-800 to-gray-900 border-gray-700' 
                        : theme === 'customer' 
                          ? 'bg-gradient-to-br from-customer-50 to-customer-100 border-customer-200' 
                          : 'bg-gradient-to-br from-white to-gray-50 border-gray-200'
                    }`}>
                    <h4 className={`font-semibold mb-4 flex items-center ${
                      theme === 'dark' 
                        ? 'text-white' 
                        : theme === 'customer' 
                          ? 'text-customer-900' 
                          : 'text-microsoft-gray'
                    }`}>
                      <Building2 className={`h-5 w-5 mr-2 ${
                        theme === 'dark' 
                          ? 'text-gray-400' 
                          : theme === 'customer' 
                            ? 'text-customer-500' 
                            : 'text-microsoft-gray'
                      }`} />
                      Documents by Company
                    </h4>
                    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
                      {Object.entries(indexStats.company_breakdown as Record<string, number>).map(([company, count]) => (
                        <div key={company} className={`p-4 rounded-lg border transition-shadow ${
                          theme === 'dark' 
                            ? 'bg-gray-700 border-gray-600 hover:shadow-lg' 
                            : theme === 'customer' 
                              ? 'bg-customer-100 border-customer-300 hover:shadow-sm' 
                              : 'bg-white border-gray-200 hover:shadow-sm'
                        }`}>
                          <div className={`font-semibold ${
                            theme === 'dark' 
                              ? 'text-white' 
                              : theme === 'customer' 
                                ? 'text-customer-900' 
                                : 'text-microsoft-gray'
                          }`}>{company}</div>
                          <div className="text-sm mt-1">
                            <Badge variant="secondary" className={`${
                              theme === 'dark' 
                                ? 'bg-gray-600 text-gray-200' 
                                : theme === 'customer' 
                                  ? 'bg-customer-200 text-customer-800' 
                                  : 'bg-gray-100 text-gray-700'
                            }`}>
                              {count} docs
                            </Badge>
                          </div>
                        </div>
                      ))}
                    </div>
                  </Card>
                )}
              </div>
            ) : (
              <div className="text-center py-8">
                <RefreshCw className="h-8 w-8 animate-spin text-gray-400 mx-auto mb-3" />
              <div className={`${
                theme === 'dark' 
                  ? 'text-gray-400' 
                  : theme === 'customer' 
                    ? 'text-customer-600' 
                    : 'text-gray-500'
              }`}>Loading statistics...</div>
            </div>
          )}
        </Card>

        <Card className={`p-8 border shadow-xl ${
            theme === 'dark' 
              ? 'bg-gradient-to-br from-gray-800 to-gray-900 border-gray-700' 
              : theme === 'customer' 
                ? 'bg-gradient-to-br from-customer-50 to-customer-100 border-customer-200' 
                : 'bg-gradient-to-br from-white to-gray-50 border-gray-200'
          }`}>
          <h3 className={`text-xl font-semibold mb-6 flex items-center ${
            theme === 'dark' 
              ? 'text-white' 
              : theme === 'customer' 
                ? 'text-customer-900' 
                : 'text-microsoft-gray'
          }`}>
            <div className={`w-6 h-6 rounded-full flex items-center justify-center mr-3 ${
              theme === 'dark' 
                ? 'bg-gray-600' 
                : theme === 'customer' 
                  ? 'bg-customer-500' 
                  : 'bg-microsoft-orange'
            }`}>
              <span className="text-white text-xs font-bold">?</span>
            </div>
            How It Works
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {[
              {
                step: 1,
                title: "Upload Document",
                description: "Upload a new document (PDF or HTML format)",
                color: theme === 'dark' ? 'bg-gray-600' : theme === 'customer' ? 'bg-customer-500' : 'bg-microsoft-blue'
              },
              {
                step: 2,
                title: "Content Extraction",
                description: "Document Intelligence extracts and structures the content",
                color: theme === 'dark' ? 'bg-gray-600' : theme === 'customer' ? 'bg-customer-600' : 'bg-microsoft-green'
              },
              {
                step: 3,
                title: "Vectorization",
                description: "Content is chunked and vectorized for optimal retrieval",
                color: theme === 'dark' ? 'bg-gray-600' : theme === 'customer' ? 'bg-customer-700' : 'bg-microsoft-purple'
              },
              {
                step: 4,
                title: "Knowledge Base Update",
                description: "Knowledge base is updated and ready for queries",
                color: theme === 'dark' ? 'bg-gray-600' : theme === 'customer' ? 'bg-customer-800' : 'bg-microsoft-orange'
              }
            ].map((item) => (
              <div key={item.step} className={`flex items-start space-x-4 p-4 rounded-lg ${
                theme === 'dark' 
                  ? 'bg-gray-700' 
                  : theme === 'customer' 
                    ? 'bg-customer-100' 
                    : 'bg-gray-50'
              }`}>
                <div className={`${item.color} text-white rounded-full w-8 h-8 flex items-center justify-center text-sm font-bold flex-shrink-0`}>
                  {item.step}
                </div>
                <div>
                  <div className={`font-semibold ${
                    theme === 'dark' 
                      ? 'text-white' 
                      : theme === 'customer' 
                        ? 'text-customer-900' 
                        : 'text-microsoft-gray'
                  }`}>{item.title}</div>
                  <div className={`text-sm mt-1 ${
                    theme === 'dark' 
                      ? 'text-gray-300' 
                      : theme === 'customer' 
                        ? 'text-customer-700' 
                        : 'text-gray-600'
                  }`}>{item.description}</div>
                </div>
              </div>
            ))}
          </div>
            </Card>
            </>
          )}

          {activeTab === 'search' && (
            <CompanySearch onDocumentsFound={(docs) => {
              console.log('Found documents:', docs);
            }} />
          )}

          {activeTab === 'admin' && (
            <>
              <Card className={`p-8 border shadow-xl ${
                  theme === 'dark' 
                    ? 'bg-gradient-to-br from-gray-800 to-gray-900 border-gray-700' 
                    : theme === 'customer' 
                      ? 'bg-gradient-to-br from-customer-50 to-customer-100 border-customer-200' 
                      : 'bg-gradient-to-br from-white to-gray-50 border-gray-200'
                }`}>
                <div className="flex items-center space-x-3 mb-6">
                  <div className={`w-10 h-10 rounded-full flex items-center justify-center ${
                    theme === 'dark' 
                      ? 'bg-red-600' 
                      : theme === 'customer' 
                        ? 'bg-red-500' 
                        : 'bg-red-500'
                  }`}>
                    <ShieldAlert className="h-5 w-5 text-white" />
                  </div>
                  <div>
                    <h3 className={`text-xl font-semibold ${
                      theme === 'dark' 
                        ? 'text-white' 
                        : theme === 'customer' 
                          ? 'text-customer-900' 
                          : 'text-microsoft-gray'
                    }`}>Administrator Controls</h3>
                    <p className={`font-medium ${
                      theme === 'dark' 
                        ? 'text-red-400' 
                        : theme === 'customer' 
                          ? 'text-red-600' 
                          : 'text-red-600'
                    }`}>⚠️ These operations can modify or delete data. Use with caution.</p>
                  </div>
                </div>

                {/* Azure Service Status */}
                <div className="mb-8">
                  <div className="flex items-center justify-between mb-4">
                    <h4 className={`font-semibold flex items-center ${
                      theme === 'dark' 
                        ? 'text-white' 
                        : theme === 'customer' 
                          ? 'text-customer-900' 
                          : 'text-microsoft-gray'
                    }`}>
                      <Database className={`h-5 w-5 mr-2 ${
                        theme === 'dark' 
                          ? 'text-gray-400' 
                          : theme === 'customer' 
                            ? 'text-customer-500' 
                            : 'text-microsoft-blue'
                      }`} />
                      Azure Service Status
                    </h4>
                    <Button
                      onClick={fetchAzureServiceStatus}
                      variant="outline"
                      size="sm"
                      className={`${
                        theme === 'dark' 
                          ? 'border-gray-600 hover:bg-gray-700 text-gray-200' 
                          : theme === 'customer' 
                            ? 'border-customer-300 hover:bg-customer-50 text-customer-700' 
                            : 'border-gray-300 hover:bg-gray-50'
                      }`}
                    >
                      <RefreshCw className="h-4 w-4 mr-2" />
                      Refresh
                    </Button>
                  </div>

                  {azureServiceStatus ? (
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                      <Card className={`p-4 ${
                        azureServiceStatus.services?.search_client 
                          ? theme === 'dark' 
                            ? 'bg-green-900/50 border-green-700' 
                            : theme === 'customer' 
                              ? 'bg-green-50 border-green-200' 
                              : 'bg-green-50 border-green-200'
                          : theme === 'dark' 
                            ? 'bg-red-900/50 border-red-700' 
                            : theme === 'customer' 
                              ? 'bg-red-50 border-red-200' 
                              : 'bg-red-50 border-red-200'
                      }`}>
                        <div className="flex items-center space-x-2">
                          <div className={`w-3 h-3 rounded-full ${azureServiceStatus.services?.search_client ? 'bg-green-500' : 'bg-red-500'}`} />
                          <span className={`font-medium ${
                            theme === 'dark' 
                              ? 'text-white' 
                              : theme === 'customer' 
                                ? 'text-customer-900' 
                                : 'text-microsoft-gray'
                          }`}>Search Client</span>
                        </div>
                        <div className={`text-sm mt-1 ${
                          theme === 'dark' 
                            ? 'text-gray-300' 
                            : theme === 'customer' 
                              ? 'text-customer-700' 
                              : 'text-gray-600'
                        }`}>
                          {azureServiceStatus.services?.search_client ? 'Connected' : 'Disconnected'}
                        </div>
                      </Card>

                      <Card className={`p-4 ${
                        azureServiceStatus.services?.form_recognizer_client 
                          ? theme === 'dark' 
                            ? 'bg-green-900/50 border-green-700' 
                            : theme === 'customer' 
                              ? 'bg-green-50 border-green-200' 
                              : 'bg-green-50 border-green-200'
                          : theme === 'dark' 
                            ? 'bg-red-900/50 border-red-700' 
                            : theme === 'customer' 
                              ? 'bg-red-50 border-red-200' 
                              : 'bg-red-50 border-red-200'
                      }`}>
                        <div className="flex items-center space-x-2">
                          <div className={`w-3 h-3 rounded-full ${azureServiceStatus.services?.form_recognizer_client ? 'bg-green-500' : 'bg-red-500'}`} />
                          <span className={`font-medium ${
                            theme === 'dark' 
                              ? 'text-white' 
                              : theme === 'customer' 
                                ? 'text-customer-900' 
                                : 'text-microsoft-gray'
                          }`}>Document Intelligence</span>
                        </div>
                        <div className={`text-sm mt-1 ${
                          theme === 'dark' 
                            ? 'text-gray-300' 
                            : theme === 'customer' 
                              ? 'text-customer-700' 
                              : 'text-gray-600'
                        }`}>
                          {azureServiceStatus.services?.form_recognizer_client ? 'Connected' : 'Disconnected'}
                        </div>
                      </Card>

                      <Card className={`p-4 ${
                        azureServiceStatus.services?.openai_client 
                          ? theme === 'dark' 
                            ? 'bg-green-900/50 border-green-700' 
                            : theme === 'customer' 
                              ? 'bg-green-50 border-green-200' 
                              : 'bg-green-50 border-green-200'
                          : theme === 'dark' 
                            ? 'bg-red-900/50 border-red-700' 
                            : theme === 'customer' 
                              ? 'bg-red-50 border-red-200' 
                              : 'bg-red-50 border-red-200'
                      }`}>
                        <div className="flex items-center space-x-2">
                          <div className={`w-3 h-3 rounded-full ${azureServiceStatus.services?.openai_client ? 'bg-green-500' : 'bg-red-500'}`} />
                          <span className={`font-medium ${
                            theme === 'dark' 
                              ? 'text-white' 
                              : theme === 'customer' 
                                ? 'text-customer-900' 
                                : 'text-microsoft-gray'
                          }`}>Azure OpenAI</span>
                        </div>
                        <div className={`text-sm mt-1 ${
                          theme === 'dark' 
                            ? 'text-gray-300' 
                            : theme === 'customer' 
                              ? 'text-customer-700' 
                              : 'text-gray-600'
                        }`}>
                          {azureServiceStatus.services?.openai_client ? 'Connected' : 'Disconnected'}
                        </div>
                      </Card>

                      <Card className={`p-4 col-span-full ${
                        azureServiceStatus.services?.using_mock_services 
                          ? theme === 'dark' 
                            ? 'bg-yellow-900/50 border-yellow-700' 
                            : theme === 'customer' 
                              ? 'bg-yellow-50 border-yellow-200' 
                              : 'bg-yellow-50 border-yellow-200'
                          : theme === 'dark' 
                            ? 'bg-gray-800/50 border-gray-700' 
                            : theme === 'customer' 
                              ? 'bg-customer-50 border-customer-200' 
                              : 'bg-blue-50 border-blue-200'
                      }`}>
                        <div className="flex items-center space-x-2">
                          <div className={`w-3 h-3 rounded-full ${azureServiceStatus.services?.using_mock_services ? 'bg-yellow-500' : theme === 'dark' ? 'bg-gray-500' : 'bg-blue-500'}`} />
                          <span className={`font-medium ${
                            theme === 'dark' 
                              ? 'text-white' 
                              : theme === 'customer' 
                                ? 'text-customer-900' 
                                : 'text-microsoft-gray'
                          }`}>Service Mode</span>
                        </div>
                        <div className={`text-sm mt-1 ${
                          theme === 'dark' 
                            ? 'text-gray-300' 
                            : theme === 'customer' 
                              ? 'text-customer-700' 
                              : 'text-gray-600'
                        }`}>
                          {azureServiceStatus.services?.using_mock_services ? 'Mock Services (Development)' : 'Real Azure Services (Production)'}
                        </div>
                      </Card>
                    </div>
                  ) : (
                    <div className="text-center py-8">
                      <RefreshCw className={`h-8 w-8 animate-spin mx-auto mb-3 ${
                        theme === 'dark' 
                          ? 'text-gray-400' 
                          : theme === 'customer' 
                            ? 'text-customer-500' 
                            : 'text-gray-400'
                      }`} />
                      <div className={`${
                        theme === 'dark' 
                          ? 'text-gray-400' 
                          : theme === 'customer' 
                            ? 'text-customer-600' 
                            : 'text-gray-500'
                      }`}>Loading service status...</div>
                    </div>
                  )}
                </div>

                {/* Index Management */}
                <div className="mb-8">
                  <h4 className={`font-semibold mb-4 flex items-center ${
                    theme === 'dark' 
                      ? 'text-white' 
                      : theme === 'customer' 
                        ? 'text-customer-900' 
                        : 'text-microsoft-gray'
                  }`}>
                    <Database className={`h-5 w-5 mr-2 ${
                      theme === 'dark' 
                        ? 'text-gray-400' 
                        : theme === 'customer' 
                          ? 'text-customer-500' 
                          : 'text-microsoft-orange'
                    }`} />
                    Search Index Management
                  </h4>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <Card className={`p-6 ${
                      theme === 'dark' 
                        ? 'bg-gray-800/50 border-gray-700' 
                        : theme === 'customer' 
                          ? 'bg-customer-50 border-customer-200' 
                          : 'bg-blue-50 border-blue-200'
                    }`}>
                      <h5 className={`font-medium mb-2 ${
                        theme === 'dark' 
                          ? 'text-white' 
                          : theme === 'customer' 
                            ? 'text-customer-900' 
                            : 'text-microsoft-gray'
                      }`}>Ensure Index Exists</h5>
                      <p className={`text-sm mb-4 ${
                        theme === 'dark' 
                          ? 'text-gray-300' 
                          : theme === 'customer' 
                            ? 'text-customer-700' 
                            : 'text-gray-600'
                      }`}>
                        Verify the search index exists and create it if missing. This won't delete existing data.
                      </p>
                      <Button
                        onClick={ensureSearchIndex}
                        disabled={isAdminOperationInProgress}
                        className={`text-white ${
                          theme === 'dark' 
                            ? 'bg-gray-600 hover:bg-gray-700' 
                            : theme === 'customer' 
                              ? 'bg-customer-500 hover:bg-customer-600' 
                              : 'bg-microsoft-blue hover:bg-microsoft-blue/90'
                        }`}
                      >
                        {isAdminOperationInProgress ? (
                          <RefreshCw className="h-4 w-4 mr-2 animate-spin" />
                        ) : (
                          <CheckCircle className="h-4 w-4 mr-2" />
                        )}
                        Ensure Index
                      </Button>
                    </Card>

                    <Card className={`p-6 ${
                      theme === 'dark' 
                        ? 'bg-red-900/50 border-red-700' 
                        : theme === 'customer' 
                          ? 'bg-red-50 border-red-200' 
                          : 'bg-red-50 border-red-200'
                    }`}>
                      <h5 className={`font-medium mb-2 flex items-center ${
                        theme === 'dark' 
                          ? 'text-white' 
                          : theme === 'customer' 
                            ? 'text-customer-900' 
                            : 'text-microsoft-gray'
                      }`}>
                        <Trash2 className="h-4 w-4 mr-2 text-red-500" />
                        Recreate Index
                      </h5>
                      <p className={`text-sm mb-4 ${
                        theme === 'dark' 
                          ? 'text-gray-300' 
                          : theme === 'customer' 
                            ? 'text-customer-700' 
                            : 'text-gray-600'
                      }`}>
                        <strong className="text-red-600">WARNING:</strong> This will delete all existing data and create a fresh index.
                      </p>
                      <Button
                        onClick={recreateSearchIndex}
                        disabled={isAdminOperationInProgress}
                        className="bg-red-500 hover:bg-red-700 text-white"
                      >
                        {isAdminOperationInProgress ? (
                          <RefreshCw className="h-4 w-4 mr-2 animate-spin" />
                        ) : (
                          <Trash2 className="h-4 w-4 mr-2" />
                        )}
                        Recreate Index
                      </Button>
                    </Card>
                  </div>
                </div>

                {/* Operation Status */}
                {adminOperationStatus && (
                  <div className={`p-4 rounded-lg border ${
                    adminOperationStatus.startsWith('Error')
                      ? theme === 'dark' 
                        ? 'bg-red-900/50 border-red-700 text-red-300' 
                        : theme === 'customer' 
                          ? 'bg-red-50 border-red-200 text-red-700' 
                          : 'bg-red-50 text-red-700 border-red-200'
                      : adminOperationStatus.startsWith('Success')
                      ? theme === 'dark' 
                        ? 'bg-green-900/50 border-green-700 text-green-300' 
                        : theme === 'customer' 
                          ? 'bg-green-50 border-green-200 text-green-700' 
                          : 'bg-green-50 text-green-700 border-green-200'
                      : theme === 'dark' 
                        ? 'bg-gray-800/50 border-gray-700 text-gray-300' 
                        : theme === 'customer' 
                          ? 'bg-customer-50 border-customer-200 text-customer-700' 
                          : 'bg-blue-50 text-blue-700 border-blue-200'
                  }`}>
                    <div className="flex items-center space-x-2">
                      {adminOperationStatus.startsWith('Error') ? (
                        <AlertCircle className="h-5 w-5 text-red-500" />
                      ) : adminOperationStatus.startsWith('Success') ? (
                        <CheckCircle className="h-5 w-5 text-green-500" />
                      ) : (
                        <Clock className={`h-5 w-5 ${theme === 'dark' ? 'text-gray-500' : 'text-blue-500'}`} />
                      )}
                      <span className="font-medium">{adminOperationStatus}</span>
                    </div>
                  </div>
                )}
              </Card>

              {/* Information Card */}
              <Card className={`p-8 border shadow-xl ${
                  theme === 'dark' 
                    ? 'bg-gradient-to-br from-gray-800 to-gray-900 border-gray-700' 
                    : theme === 'customer' 
                      ? 'bg-gradient-to-br from-customer-50 to-customer-100 border-customer-200' 
                      : 'bg-gradient-to-br from-white to-gray-50 border-gray-200'
                }`}>
                <h3 className={`text-xl font-semibold mb-6 flex items-center ${
                  theme === 'dark' 
                    ? 'text-white' 
                    : theme === 'customer' 
                      ? 'text-customer-900' 
                      : 'text-microsoft-gray'
                }`}>
                  <div className={`w-6 h-6 rounded-full flex items-center justify-center mr-3 ${
                    theme === 'dark' 
                      ? 'bg-gray-600' 
                      : theme === 'customer' 
                        ? 'bg-customer-500' 
                        : 'bg-microsoft-orange'
                  }`}>
                    <span className="text-white text-xs font-bold">ℹ</span>
                  </div>
                  About the Modular System
                </h3>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  <div>
                    <h4 className={`font-semibold mb-3 ${
                      theme === 'dark' 
                        ? 'text-white' 
                        : theme === 'customer' 
                          ? 'text-customer-900' 
                          : 'text-microsoft-gray'
                    }`}>Enhanced Features</h4>
                    <ul className="space-y-2 text-sm">
                      <li className="flex items-center space-x-2">
                        <CheckCircle className="h-4 w-4 text-green-500" />
                        <span className={`${
                          theme === 'dark' 
                            ? 'text-gray-300' 
                            : theme === 'customer' 
                              ? 'text-customer-700' 
                              : 'text-gray-600'
                        }`}>Centralized Azure Service Management</span>
                      </li>
                      <li className="flex items-center space-x-2">
                        <CheckCircle className="h-4 w-4 text-green-500" />
                        <span className={`${
                          theme === 'dark' 
                            ? 'text-gray-300' 
                            : theme === 'customer' 
                              ? 'text-customer-700' 
                              : 'text-gray-600'
                        }`}>Enhanced Search Index Schema</span>
                      </li>
                      <li className="flex items-center space-x-2">
                        <CheckCircle className="h-4 w-4 text-green-500" />
                        <span className={`${
                          theme === 'dark' 
                            ? 'text-gray-300' 
                            : theme === 'customer' 
                              ? 'text-customer-700' 
                              : 'text-gray-600'
                        }`}>Vector Embeddings with Azure OpenAI</span>
                      </li>
                      <li className="flex items-center space-x-2">
                        <CheckCircle className="h-4 w-4 text-green-500" />
                        <span className={`${
                          theme === 'dark' 
                            ? 'text-gray-300' 
                            : theme === 'customer' 
                              ? 'text-customer-700' 
                              : 'text-gray-600'
                        }`}>Document Intelligence Integration</span>
                      </li>
                    </ul>
                  </div>
                  <div>
                    <h4 className={`font-semibold mb-3 ${
                      theme === 'dark' 
                        ? 'text-white' 
                        : theme === 'customer' 
                          ? 'text-customer-900' 
                          : 'text-microsoft-gray'
                    }`}>System Architecture</h4>
                    <ul className="space-y-2 text-sm">
                      <li className="flex items-center space-x-2">
                        <Zap className={`h-4 w-4 ${
                          theme === 'dark' 
                            ? 'text-gray-400' 
                            : theme === 'customer' 
                              ? 'text-customer-500' 
                              : 'text-microsoft-blue'
                        }`} />
                        <span className={`${
                          theme === 'dark' 
                            ? 'text-gray-300' 
                            : theme === 'customer' 
                              ? 'text-customer-700' 
                              : 'text-gray-600'
                        }`}>Modular Azure Services Layer</span>
                      </li>
                      <li className="flex items-center space-x-2">
                        <Zap className={`h-4 w-4 ${
                          theme === 'dark' 
                            ? 'text-gray-400' 
                            : theme === 'customer' 
                              ? 'text-customer-500' 
                              : 'text-microsoft-blue'
                        }`} />
                        <span className={`${
                          theme === 'dark' 
                            ? 'text-gray-300' 
                            : theme === 'customer' 
                              ? 'text-customer-700' 
                              : 'text-gray-600'
                        }`}>Enhanced Document Processing Pipeline</span>
                      </li>
                      <li className="flex items-center space-x-2">
                        <Zap className={`h-4 w-4 ${
                          theme === 'dark' 
                            ? 'text-gray-400' 
                            : theme === 'customer' 
                              ? 'text-customer-500' 
                              : 'text-microsoft-blue'
                        }`} />
                        <span className={`${
                          theme === 'dark' 
                            ? 'text-gray-300' 
                            : theme === 'customer' 
                              ? 'text-customer-700' 
                              : 'text-gray-600'
                        }`}>Real-time Progress Tracking</span>
                      </li>
                      <li className="flex items-center space-x-2">
                        <Zap className={`h-4 w-4 ${
                          theme === 'dark' 
                            ? 'text-gray-400' 
                            : theme === 'customer' 
                              ? 'text-customer-500' 
                              : 'text-microsoft-blue'
                        }`} />
                        <span className={`${
                          theme === 'dark' 
                            ? 'text-gray-300' 
                            : theme === 'customer' 
                              ? 'text-customer-700' 
                              : 'text-gray-600'
                        }`}>Comprehensive Error Handling</span>
                      </li>
                    </ul>
                  </div>
                </div>
              </Card>
            </>
          )}
        </div>
      </div>
    </ChatLayout>
  );
}
