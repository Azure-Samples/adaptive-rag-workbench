import React, { useState, useCallback, useRef } from 'react';
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Badge } from "@/components/ui/badge";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { 
  FileText, 
  Upload, 
  X, 
  Check, 
  AlertCircle, 
  Clock, 
  RefreshCw,
  ChevronDown,
  ChevronUp
} from 'lucide-react';

interface DocumentFile {
  id: string;
  file: File;
  status: 'pending' | 'processing' | 'completed' | 'error';
  processingId?: string;
  error?: string;
  progress?: number;
  result?: any;
}

interface ProcessingStatus {
  processing_id: string;
  filename: string;
  status: 'pending' | 'processing' | 'completed' | 'error';
  progress: number;
  start_time: string;
  end_time?: string;
  error_message?: string;
  chunks_created?: number;
}

interface BatchProcessingStatus {
  batch_id: string;
  total_documents: number;
  completed_documents: number;
  failed_documents: number;
  results: ProcessingStatus[];
  start_time: string;
  end_time?: string;
}

interface DocumentUploadResponse {
  processing_ids?: string[];
  batch_id?: string;
  message: string;
  status?: string;
  uploaded_files?: any[];
}

export const DocumentUpload: React.FC = () => {
  const [files, setFiles] = useState<DocumentFile[]>([]);
  const [isUploading, setIsUploading] = useState(false);
  const [batchProcessing, setBatchProcessing] = useState(true);
  const [uploadResponse, setUploadResponse] = useState<DocumentUploadResponse | null>(null);
  const [batchStatus, setBatchStatus] = useState<BatchProcessingStatus | null>(null);
  const [showDetails, setShowDetails] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'completed': return 'bg-green-100 text-green-800 border-green-200';
      case 'processing': return 'bg-blue-100 text-blue-800 border-blue-200';
      case 'error': return 'bg-red-100 text-red-800 border-red-200';
      default: return 'bg-gray-100 text-gray-800 border-gray-200';
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'completed': return <Check className="w-4 h-4" />;
      case 'processing': return <RefreshCw className="w-4 h-4 animate-spin" />;
      case 'error': return <AlertCircle className="w-4 h-4" />;
      default: return <Clock className="w-4 h-4" />;
    }
  };

  const validateFile = (file: File): string | null => {
    const allowedTypes = ['application/pdf', 'text/html', 'application/msword', 
                         'application/vnd.openxmlformats-officedocument.wordprocessingml.document'];
    
    if (!allowedTypes.includes(file.type)) {
      return 'Unsupported file type. Please upload PDF, HTML, or Word documents.';
    }
    
    if (file.size > 50 * 1024 * 1024) { // 50MB
      return 'File size must be less than 50MB.';
    }
    
    return null;
  };

  const handleFileSelect = useCallback((event: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFiles = Array.from(event.target.files || []);
    const newFiles: DocumentFile[] = [];
    
    selectedFiles.forEach(file => {
      const validationError = validateFile(file);
      if (validationError) {
        setError(validationError);
        return;
      }
      
      const documentFile: DocumentFile = {
        id: `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
        file,
        status: 'pending'
      };
      
      newFiles.push(documentFile);
    });
    
    setFiles(prev => [...prev, ...newFiles]);
    setError(null);
    
    // Clear the input
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  }, []);

  const removeFile = useCallback((id: string) => {
    setFiles(prev => prev.filter(file => file.id !== id));
  }, []);

  const clearAll = useCallback(() => {
    setFiles([]);
    setUploadResponse(null);
    setBatchStatus(null);
    setError(null);
  }, []);



  const handleUpload = useCallback(async () => {
    if (files.length === 0) return;
    
    setIsUploading(true);
    setError(null);
    
    try {
      const formData = new FormData();
      
      // For now, handle single file upload using existing API
      if (files.length === 1) {
        formData.append('file', files[0].file);
        
        const response = await fetch('/api/upload', {
          method: 'POST',
          body: formData
        });
        
        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const result = await response.json();
        
        if (result.status === 'success') {
          // Update file status to completed
          setFiles(prev => prev.map((file) => ({
            ...file,
            status: 'completed',
            progress: 100,
            result: result
          })));
          
          setUploadResponse({
            status: 'success',
            message: `Successfully uploaded ${result.filename}. ${result.message}`,
            uploaded_files: [result]
          });
        } else {
          throw new Error(result.message || 'Upload failed');
        }
        
        setIsUploading(false);
        return;
      }
      
      // For multiple files, upload them one by one using existing API
      for (let i = 0; i < files.length; i++) {
        const fileFormData = new FormData();
        fileFormData.append('file', files[i].file);
        
        // Update file status to processing
        setFiles(prev => prev.map((file, index) => 
          index === i ? { ...file, status: 'processing', progress: 0 } : file
        ));
        
        try {
          const response = await fetch('/api/upload', {
            method: 'POST',
            body: fileFormData
          });
          
          if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
          }
          
          const result = await response.json();
          
          if (result.status === 'success') {
            // Update file status to completed
            setFiles(prev => prev.map((file, index) => 
              index === i ? { ...file, status: 'completed', progress: 100, result } : file
            ));
          } else {
            throw new Error(result.message || 'Upload failed');
          }
          
        } catch (error) {
          // Update file status to error
          setFiles(prev => prev.map((file, index) => 
            index === i ? { 
              ...file, 
              status: 'error', 
              error: error instanceof Error ? error.message : 'Upload failed'
            } : file
          ));
        }
      }
      
      // Calculate results for multiple files
      const successful = files.filter(f => f.status === 'completed').length;
      const failed = files.filter(f => f.status === 'error').length;
      
      if (successful > 0) {
        setUploadResponse({
          status: 'success',
          message: `Successfully uploaded ${successful} file${successful !== 1 ? 's' : ''}${failed > 0 ? ` (${failed} failed)` : ''}`,
          uploaded_files: files.filter(f => f.status === 'completed').map(f => f.result).filter(Boolean)
        });
      } else if (failed > 0) {
        setError(`All ${failed} file${failed !== 1 ? 's' : ''} failed to upload`);
      }
      
      setIsUploading(false);
      
    } catch (error) {
      console.error('Upload error:', error);
      setError(error instanceof Error ? error.message : 'Upload failed');
      setIsUploading(false);
    }
  }, [files]);

  const formatFileSize = (bytes: number): string => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  const getOverallProgress = (): number => {
    if (files.length === 0) return 0;
    const totalProgress = files.reduce((sum, file) => sum + (file.progress || 0), 0);
    return Math.round(totalProgress / files.length);
  };

  return (
    <div className="max-w-4xl mx-auto p-6 space-y-6">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Upload className="w-5 h-5" />
            Document Upload
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* File Upload Area */}
          <div className="border-2 border-dashed border-gray-300 rounded-lg p-8 text-center hover:border-gray-400 transition-colors">
            <input
              type="file"
              ref={fileInputRef}
              onChange={handleFileSelect}
              multiple
              accept=".pdf,.html,.doc,.docx"
              className="hidden"
            />
            <FileText className="w-12 h-12 mx-auto mb-4 text-gray-400" />
            <p className="text-lg font-medium mb-2">Drop files here or click to browse</p>
            <p className="text-sm text-gray-600 mb-4">
              Supports PDF, HTML, and Word documents (max 50MB each)
            </p>
            <Button
              onClick={() => fileInputRef.current?.click()}
              variant="outline"
              disabled={isUploading}
            >
              Select Files
            </Button>
          </div>

          {/* Batch Processing Toggle */}
          <div className="flex items-center gap-2">
            <input
              type="checkbox"
              id="batch-processing"
              checked={batchProcessing}
              onChange={(e) => setBatchProcessing(e.target.checked)}
              disabled={isUploading}
              className="rounded"
            />
            <label htmlFor="batch-processing" className="text-sm font-medium">
              Enable batch processing (recommended for multiple files)
            </label>
          </div>

          {/* Selected Files */}
          {files.length > 0 && (
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <h3 className="font-medium">Selected Files ({files.length})</h3>
                <Button
                  onClick={clearAll}
                  variant="outline"
                  size="sm"
                  disabled={isUploading}
                >
                  Clear All
                </Button>
              </div>
              
              <div className="space-y-2 max-h-64 overflow-y-auto">
                {files.map((docFile) => (
                  <div
                    key={docFile.id}
                    className="flex items-center justify-between p-3 bg-gray-50 rounded-lg"
                  >
                    <div className="flex items-center gap-3 flex-1">
                      <FileText className="w-5 h-5 text-gray-500" />
                      <div className="flex-1 min-w-0">
                        <p className="font-medium truncate">{docFile.file.name}</p>
                        <p className="text-sm text-gray-600">
                          {formatFileSize(docFile.file.size)}
                        </p>
                      </div>
                    </div>
                    
                    <div className="flex items-center gap-2">
                      <Badge
                        variant="outline"
                        className={getStatusColor(docFile.status)}
                      >
                        {getStatusIcon(docFile.status)}
                        <span className="ml-1 capitalize">{docFile.status}</span>
                      </Badge>
                      
                      {docFile.progress !== undefined && docFile.status === 'processing' && (
                        <div className="w-16 text-xs text-gray-600">
                          {docFile.progress}%
                        </div>
                      )}
                      
                      {!isUploading && docFile.status === 'pending' && (
                        <Button
                          onClick={() => removeFile(docFile.id)}
                          variant="ghost"
                          size="sm"
                        >
                          <X className="w-4 h-4" />
                        </Button>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Upload Button */}
          {files.length > 0 && (
            <Button
              onClick={handleUpload}
              disabled={isUploading || files.length === 0}
              className="w-full"
            >
              {isUploading ? (
                <>
                  <RefreshCw className="w-4 h-4 mr-2 animate-spin" />
                  Processing...
                </>
              ) : (
                <>
                  <Upload className="w-4 h-4 mr-2" />
                  Upload & Process {files.length} {files.length === 1 ? 'Document' : 'Documents'}
                </>
              )}
            </Button>
          )}

          {/* Error Message */}
          {error && (
            <Alert variant="destructive">
              <AlertCircle className="w-4 h-4" />
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}

          {/* Upload Response */}
          {uploadResponse && (
            <Alert>
              <Check className="w-4 h-4" />
              <AlertDescription>{uploadResponse.message}</AlertDescription>
            </Alert>
          )}
        </CardContent>
      </Card>

      {/* Processing Status */}
      {(batchStatus || isUploading) && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center justify-between">
              <span>Processing Status</span>
              {batchStatus && (
                <Button
                  onClick={() => setShowDetails(!showDetails)}
                  variant="ghost"
                  size="sm"
                >
                  {showDetails ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                  Details
                </Button>
              )}
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {/* Overall Progress */}
            <div className="space-y-2">
              <div className="flex justify-between text-sm">
                <span>Overall Progress</span>
                <span>{getOverallProgress()}%</span>
              </div>
              <Progress value={getOverallProgress()} className="w-full" />
            </div>

            {/* Batch Summary */}
            {batchStatus && (
              <div className="grid grid-cols-3 gap-4 text-center">
                <div className="p-3 bg-blue-50 rounded-lg">
                  <div className="text-2xl font-bold text-blue-600">
                    {batchStatus.total_documents}
                  </div>
                  <div className="text-sm text-blue-600">Total</div>
                </div>
                <div className="p-3 bg-green-50 rounded-lg">
                  <div className="text-2xl font-bold text-green-600">
                    {batchStatus.completed_documents}
                  </div>
                  <div className="text-sm text-green-600">Completed</div>
                </div>
                <div className="p-3 bg-red-50 rounded-lg">
                  <div className="text-2xl font-bold text-red-600">
                    {batchStatus.failed_documents}
                  </div>
                  <div className="text-sm text-red-600">Failed</div>
                </div>
              </div>
            )}

            {/* Detailed Status */}
            {showDetails && batchStatus && (
              <div className="space-y-2">
                <h4 className="font-medium">Document Details</h4>
                <div className="space-y-2 max-h-64 overflow-y-auto">
                  {batchStatus.results.map((result) => (
                    <div
                      key={result.processing_id}
                      className="flex items-center justify-between p-3 bg-gray-50 rounded-lg"
                    >
                      <div className="flex items-center gap-3 flex-1">
                        <FileText className="w-4 h-4 text-gray-500" />
                        <div className="flex-1 min-w-0">
                          <p className="font-medium truncate">{result.filename}</p>
                          {result.error_message && (
                            <p className="text-sm text-red-600">{result.error_message}</p>
                          )}
                        </div>
                      </div>
                      
                      <div className="flex items-center gap-2">
                        <Badge
                          variant="outline"
                          className={getStatusColor(result.status)}
                        >
                          {getStatusIcon(result.status)}
                          <span className="ml-1 capitalize">{result.status}</span>
                        </Badge>
                        
                        {result.progress !== undefined && result.status === 'processing' && (
                          <div className="w-16 text-xs text-gray-600">
                            {result.progress}%
                          </div>
                        )}
                        
                        {result.chunks_created && (
                          <div className="text-xs text-gray-600">
                            {result.chunks_created} chunks
                          </div>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  );
};
