import { useState, useEffect } from 'react';
import { Card } from './ui/card';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Checkbox } from './ui/checkbox';
import { Search, FileText, Calendar, Building2, Download, ExternalLink, Loader2, Globe, Play } from 'lucide-react';
import { apiService } from '../services/api';

interface DocumentResult {
  id: string;
  title: string;
  company: string;
  document_type: string;
  filing_date: string;
  cik: string;
  url?: string;
  content?: string;
  source?: string;
  last_updated?: string;
  period_end_date?: string;
  file_size?: number;
  year?: number;
}

interface CompanySearchProps {
  onDocumentsFound: (documents: DocumentResult[]) => void;
}

interface SearchFilters {
  company: string;
  documentTypes: string[];
  years: number[];
  searchType: 'company' | 'website';
}

export function CompanySearch({ onDocumentsFound }: CompanySearchProps) {
  const [searchFilters, setSearchFilters] = useState<SearchFilters>({
    company: '',
    documentTypes: ['10-K'],
    years: [new Date().getFullYear()],
    searchType: 'company'
  });
  const [isSearching, setIsSearching] = useState(false);
  const [searchResults, setSearchResults] = useState<DocumentResult[]>([]);
  
  // Batch processing state
  const [selectedDocuments, setSelectedDocuments] = useState<Set<string>>(new Set());
  const [isBatchProcessing, setIsBatchProcessing] = useState(false);
  const [batchProgress, setBatchProgress] = useState<{
    batch_id: string;
    total_documents: number;
    completed_documents: number;
    failed_documents: number;
    overall_progress_percent: number;
    status: string;
    message?: string;
    current_processing: Array<{
      document_id: string;
      ticker: string;
      accession_number: string;
      stage: string;
      progress_percent: number;
      message: string;
    }>;
  } | null>(null);
  const [batchError, setBatchError] = useState<string | null>(null);
  const [pollingInterval, setPollingInterval] = useState<NodeJS.Timeout | null>(null);

  const availableDocumentTypes = [
    { value: '10-K', label: '10-K (Annual Report)', description: 'Comprehensive annual business and financial report' },
    { value: '10-Q', label: '10-Q (Quarterly Report)', description: 'Quarterly financial report' },
    { value: '8-K', label: '8-K (Current Report)', description: 'Report of major events or corporate changes' },
    { value: '10-K/A', label: '10-K/A (Annual Report Amendment)', description: 'Amendment to annual report' },
    { value: '10-Q/A', label: '10-Q/A (Quarterly Report Amendment)', description: 'Amendment to quarterly report' },
    { value: 'DEF 14A', label: 'DEF 14A (Proxy Statement)', description: 'Proxy statement for shareholder meetings' },
    { value: '20-F', label: '20-F (Foreign Annual)', description: 'Annual report for foreign companies' }
  ];

  const currentYear = new Date().getFullYear();
  const availableYears = Array.from({ length: 10 }, (_, i) => currentYear - i);

  const searchTypes = [
    { value: 'company', label: 'Company Documents', icon: Building2, description: 'Search SEC filings by company ticker or name' },
    { value: 'website', label: 'Website Content', icon: Globe, description: 'Search and process content from company websites' }
  ];

  const handleDocTypeChange = (docType: string, checked: boolean) => {
    setSearchFilters(prev => ({
      ...prev,
      documentTypes: checked 
        ? [...prev.documentTypes, docType]
        : prev.documentTypes.filter(type => type !== docType)
    }));
  };

  const handleYearChange = (year: number, checked: boolean) => {
    setSearchFilters(prev => ({
      ...prev,
      years: checked 
        ? [...prev.years, year]
        : prev.years.filter(y => y !== year)
    }));
  };

  const selectAllYears = () => {
    setSearchFilters(prev => ({ ...prev, years: availableYears }));
  };

  const clearAllYears = () => {
    setSearchFilters(prev => ({ ...prev, years: [] }));
  };

  const selectRecentYears = () => {
    const recentYears = availableYears.slice(0, 5); // Last 5 years
    setSearchFilters(prev => ({ ...prev, years: recentYears }));
  };

  const selectAllDocTypes = () => {
    setSearchFilters(prev => ({ ...prev, documentTypes: availableDocumentTypes.map(dt => dt.value) }));
  };

  const clearAllDocTypes = () => {
    setSearchFilters(prev => ({ ...prev, documentTypes: [] }));
  };

  const handleSearchTypeChange = (searchType: 'company' | 'website') => {
    setSearchFilters(prev => ({ ...prev, searchType }));
  };

  const handleProcessDocument = async (doc: DocumentResult) => {
    try {
      const response = await fetch('/api/v1/sec/documents/process', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          ticker: doc.company,
          accession_number: doc.id,
          form_type: doc.document_type,
          document_url: doc.url
        })
      });

      if (!response.ok) {
        throw new Error(`Processing failed: ${response.statusText}`);
      }

      const result = await response.json();
      console.log(`Document processing ${result.status}: ${result.message}`);
    } catch (error) {
      console.error('Processing failed:', error);
    }
  };

  const handleViewDocument = (doc: DocumentResult) => {
    if (doc.url) {
      window.open(doc.url, '_blank');
    } else {
      console.error('Document URL not available');
    }
  };

  // Batch processing functions
  const toggleDocumentSelection = (documentId: string) => {
    setSelectedDocuments(prev => {
      const newSelection = new Set(prev);
      if (newSelection.has(documentId)) {
        newSelection.delete(documentId);
      } else {
        newSelection.add(documentId);
      }
      return newSelection;
    });
  };

  const selectAllDocuments = () => {
    setSelectedDocuments(new Set(searchResults.map(doc => doc.id)));
  };

  const clearDocumentSelection = () => {
    setSelectedDocuments(new Set());
  };

  const processSelectedDocuments = async () => {
    if (selectedDocuments.size === 0) {
      setBatchError('Please select at least one document to process');
      return;
    }

    setIsBatchProcessing(true);
    setBatchError(null);
    
    try {
      // Prepare the batch request
      const selectedDocs = searchResults.filter(doc => selectedDocuments.has(doc.id));
      const filings = selectedDocs.map(doc => ({
        ticker: doc.company,
        accession_number: doc.id,
        document_id: doc.id
      }));

      // Start batch processing
      const batchResponse = await apiService.processMultipleSECDocuments({
        filings,
        max_parallel: 3
      });

      // Start polling for progress
      startProgressPolling(batchResponse.batch_id);
      
    } catch (error) {
      console.error('Batch processing failed:', error);
      setBatchError(error instanceof Error ? error.message : 'Batch processing failed');
      setIsBatchProcessing(false);
    }
  };

  const startProgressPolling = (batchId: string) => {
    // Clear any existing interval
    if (pollingInterval) {
      clearInterval(pollingInterval);
      setPollingInterval(null);
    }

    let currentInterval: NodeJS.Timeout | null = null;

    const pollProgress = async () => {
      try {
        const status = await apiService.getBatchStatus(batchId);
        setBatchProgress(status);
        
        if (status.status === 'completed' || status.status === 'failed') {
          // Clear interval immediately to prevent multiple calls
          if (currentInterval) {
            clearInterval(currentInterval);
            setPollingInterval(null);
          }
          setIsBatchProcessing(false);
          
          if (status.status === 'completed') {
            console.log(`Batch processing completed! ${status.completed_documents} documents processed successfully.`);
            // Show completion message in the UI
            setBatchProgress({
              ...status,
              status: 'completed',
              message: `✅ Batch processing completed! ${status.completed_documents} documents processed successfully.`
            });
            // Clear selections after successful processing
            setSelectedDocuments(new Set());
          } else {
            setBatchError(`Batch processing failed: ${status.error_message || 'Unknown error'}`);
          }
          return; // Exit early to prevent setting up new interval
        }
      } catch (error) {
        console.error('Failed to get batch status:', error);
        setBatchError(error instanceof Error ? error.message : 'Failed to get batch status');
        if (currentInterval) {
          clearInterval(currentInterval);
          setPollingInterval(null);
        }
        setIsBatchProcessing(false);
        return; // Exit early on error
      }
    };

    // Poll immediately and then every 2 seconds
    pollProgress();
    currentInterval = setInterval(pollProgress, 2000);
    setPollingInterval(currentInterval);
  };

  // Cleanup polling on unmount
  useEffect(() => {
    return () => {
      if (pollingInterval) {
        clearInterval(pollingInterval);
      }
    };
  }, []); // Empty dependency array so it only runs on unmount

  const handleSearch = async () => {
    if (!searchFilters.company.trim()) {
      setBatchError('Please enter a company name or ticker');
      return;
    }
    
    if (searchFilters.searchType === 'company' && 
        (searchFilters.documentTypes.length === 0 || searchFilters.years.length === 0)) {
      setBatchError('Please select at least one document type and year for company search');
      return;
    }
    
    setIsSearching(true);
    setSearchResults([]);
    setBatchError(null); // Clear any previous errors
    
    try {
      if (searchFilters.searchType === 'company') {
        // Use SEC documents API for company search
        const response = await fetch('/api/v1/sec/filings/specific', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            ticker: searchFilters.company,
            form_types: searchFilters.documentTypes,  // backend expects form_types (plural)
            years: searchFilters.years,               // backend expects years (plural)
            limit: 50
          })
        });
        
        if (!response.ok) {
          throw new Error(`Search failed: ${response.statusText}`);
        }
        
        const data = await response.json();
        const results = (data.filings || []).map((filing: any) => ({
          id: filing.accession_number,
          title: `${filing.form_type} - ${filing.company_name}`,
          company: filing.company_name,
          document_type: filing.form_type,
          filing_date: filing.filing_date,
          cik: filing.cik,
          url: filing.document_url,
          period_end_date: filing.period_end_date,
          file_size: filing.file_size,
          year: filing.year
        }));
        setSearchResults(results);
        onDocumentsFound(results);
      } else {
        // Use legacy API for website search
        const response = await fetch('/api/companies/search', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            company: searchFilters.company,
            searchType: searchFilters.searchType
          })
        });
        
        if (!response.ok) {
          throw new Error(`Search failed: ${response.statusText}`);
        }
        
        const resultsData = await response.json();
        setSearchResults(resultsData.documents || []);
        onDocumentsFound(resultsData.documents || []);
      }
      
      console.log(`Search complete: Found ${searchResults.length} results for ${searchFilters.company}`);
    } catch (error) {
      console.error('Search failed:', error);
      setBatchError(error instanceof Error ? error.message : 'Search failed. Please try again.');
      setSearchResults([]);
    } finally {
      setIsSearching(false);
    }
  };

  return (
    <Card className="p-8 bg-gradient-to-br from-white to-gray-50 border-gray-200 shadow-xl">
      <div className="flex items-center space-x-4 mb-8">
        <div className="w-12 h-12 bg-gradient-to-br from-microsoft-purple to-purple-600 rounded-xl flex items-center justify-center shadow-lg">
          <Search className="h-6 w-6 text-white" />
        </div>
        <div>
          <h3 className="text-2xl font-bold text-microsoft-gray">Document Search & Process</h3>
          <p className="text-gray-600 mt-1">Search for SEC filings and website content, then process them into the vector store with intelligent chunking and metadata extraction</p>
        </div>
      </div>

      <div className="space-y-6">
        {/* Search Type Selection */}
        <div className="bg-white p-6 rounded-xl border border-gray-200 shadow-sm">
          <label className="block text-sm font-semibold text-gray-800 mb-4">
            Search Type
          </label>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {searchTypes.map((type) => {
              const IconComponent = type.icon;
              return (
                <div 
                  key={type.value}
                  className={`p-4 rounded-lg border-2 cursor-pointer transition-all duration-200 ${
                    searchFilters.searchType === type.value
                      ? 'border-microsoft-purple bg-microsoft-purple/5 shadow-md'
                      : 'border-gray-200 hover:border-microsoft-purple/30 hover:bg-gray-50'
                  }`}
                  onClick={() => handleSearchTypeChange(type.value as 'company' | 'website')}
                >
                  <div className="flex items-center space-x-3">
                    <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${
                      searchFilters.searchType === type.value
                        ? 'bg-microsoft-purple text-white'
                        : 'bg-gray-100 text-gray-600'
                    }`}>
                      <IconComponent className="h-5 w-5" />
                    </div>
                    <div>
                      <h4 className="font-semibold text-gray-800">{type.label}</h4>
                      <p className="text-sm text-gray-600">{type.description}</p>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Company/Website Input */}
        <div className="bg-white p-6 rounded-xl border border-gray-200 shadow-sm">
          <label className="block text-sm font-semibold text-gray-800 mb-3">
            {searchFilters.searchType === 'company' ? 'Company Ticker or Name' : 'Website URL or Company Name'}
          </label>
          <Input
            type="text"
            placeholder={searchFilters.searchType === 'company' 
              ? "e.g., AAPL, Apple Inc., Microsoft Corporation"
              : "e.g., apple.com, https://investor.apple.com, Microsoft Corporation"
            }
            value={searchFilters.company}
            onChange={(e) => setSearchFilters(prev => ({ ...prev, company: e.target.value }))}
            onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
            className="w-full h-12 text-lg border-2 border-gray-200 focus:border-microsoft-purple focus:ring-2 focus:ring-microsoft-purple/20 rounded-lg"
          />
          <p className="text-xs text-gray-500 mt-2">
            {searchFilters.searchType === 'company' 
              ? 'Enter a company ticker symbol or full company name'
              : 'Enter a website URL or company name to search for relevant web content'
            }
          </p>
        </div>

        {/* Document Types - Only show for company search */}
        {searchFilters.searchType === 'company' && (
          <div className="bg-white p-6 rounded-xl border border-gray-200 shadow-sm">
            <div className="flex items-center justify-between mb-4">
              <label className="block text-sm font-semibold text-gray-800">
                Document Types
              </label>
              <div className="flex space-x-2">
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={selectAllDocTypes}
                  className="text-xs px-3 py-1 h-7"
                >
                  Select All
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={clearAllDocTypes}
                  className="text-xs px-3 py-1 h-7"
                >
                  Clear All
                </Button>
              </div>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
              {availableDocumentTypes.map((docType) => (
                <div key={docType.value} className="flex items-start space-x-3 p-3 rounded-lg border border-gray-100 hover:border-microsoft-purple/30 hover:bg-microsoft-purple/5 transition-colors">
                  <Checkbox
                    id={docType.value}
                    checked={searchFilters.documentTypes.includes(docType.value)}
                    onCheckedChange={(checked) => handleDocTypeChange(docType.value, checked as boolean)}
                    className="mt-1"
                  />
                  <div className="flex-1">
                    <label htmlFor={docType.value} className="text-sm font-medium text-gray-800 cursor-pointer block">
                      {docType.label}
                    </label>
                    <p className="text-xs text-gray-500 mt-1">{docType.description}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Years - Only show for company search */}
        {searchFilters.searchType === 'company' && (
          <div className="bg-white p-6 rounded-xl border border-gray-200 shadow-sm">
            <div className="flex items-center justify-between mb-4">
              <label className="block text-sm font-semibold text-gray-800">
                Years
              </label>
              <div className="flex space-x-2">
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={selectRecentYears}
                  className="text-xs px-3 py-1 h-7"
                >
                  Recent 5 Years
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={selectAllYears}
                  className="text-xs px-3 py-1 h-7"
                >
                  Select All Years
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={clearAllYears}
                  className="text-xs px-3 py-1 h-7"
                >
                  Clear All Years
                </Button>
              </div>
            </div>
            <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-5 gap-3">
              {availableYears.map((year) => (
                <div key={year} className="flex items-center space-x-2 p-3 rounded-lg border border-gray-100 hover:border-microsoft-purple/30 hover:bg-microsoft-purple/5 transition-colors">
                  <Checkbox
                    id={`year-${year}`}
                    checked={searchFilters.years.includes(year)}
                    onCheckedChange={(checked) => handleYearChange(year, checked as boolean)}
                  />
                  <label htmlFor={`year-${year}`} className="text-sm font-medium text-gray-700 cursor-pointer">
                    {year}
                  </label>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Search Button */}
        <div className="bg-white p-6 rounded-xl border border-gray-200 shadow-sm">
          <Button
            onClick={handleSearch}
            disabled={isSearching || !searchFilters.company.trim() || 
              (searchFilters.searchType === 'company' && (searchFilters.documentTypes.length === 0 || searchFilters.years.length === 0))}
            className="w-full h-14 text-lg font-semibold bg-gradient-to-r from-microsoft-purple to-purple-600 hover:from-microsoft-purple/90 hover:to-purple-600/90 shadow-lg hover:shadow-xl transition-all duration-200"
          >
            {isSearching ? (
              <>
                <Loader2 className="h-5 w-5 mr-3 animate-spin" />
                {searchFilters.searchType === 'company' ? 'Searching SEC Filings...' : 'Searching Website Content...'}
              </>
            ) : (
              <>
                <Search className="h-5 w-5 mr-3" />
                {searchFilters.searchType === 'company' ? 'Search SEC Filings' : 'Search Website Content'}
              </>
            )}
          </Button>
          {(!searchFilters.company.trim() || 
            (searchFilters.searchType === 'company' && (searchFilters.documentTypes.length === 0 || searchFilters.years.length === 0))) && (
            <p className="text-xs text-gray-500 mt-2 text-center">
              {searchFilters.searchType === 'company' 
                ? 'Please enter a company name and select at least one document type and year'
                : 'Please enter a website URL or company name to search'
              }
            </p>
          )}
        </div>

        {/* Search Results */}
        {searchResults.length > 0 && (
          <div className="bg-white p-6 rounded-xl border border-gray-200 shadow-sm">
            <div className="flex items-center justify-between mb-6">
              <h4 className="text-xl font-bold text-microsoft-gray">
                Found {searchResults.length} Documents
              </h4>
              <div className="flex items-center space-x-2 text-sm text-gray-500">
                <FileText className="h-4 w-4" />
                <span>Ready for processing</span>
              </div>
            </div>

            {/* Batch Processing Controls - Only for company search */}
            {searchFilters.searchType === 'company' && (
              <div className="mb-6 p-4 bg-gradient-to-r from-microsoft-purple/5 to-purple-50 rounded-xl border border-microsoft-purple/20">
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-4">
                    <div className="flex items-center space-x-2">
                      <Checkbox
                        id="select-all"
                        checked={selectedDocuments.size === searchResults.length && searchResults.length > 0}
                        onCheckedChange={(checked) => {
                          if (checked) {
                            selectAllDocuments();
                          } else {
                            clearDocumentSelection();
                          }
                        }}
                      />
                      <label htmlFor="select-all" className="text-sm font-medium text-gray-700 cursor-pointer">
                        Select All ({selectedDocuments.size} of {searchResults.length})
                      </label>
                    </div>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={clearDocumentSelection}
                      disabled={selectedDocuments.size === 0}
                      className="text-xs px-3 py-1 h-7"
                    >
                      Clear Selection
                    </Button>
                  </div>
                  <Button
                    onClick={processSelectedDocuments}
                    disabled={selectedDocuments.size === 0 || isBatchProcessing}
                    className="bg-gradient-to-r from-microsoft-purple to-purple-600 hover:from-microsoft-purple/90 hover:to-purple-600/90 text-white px-4 py-2 rounded-lg font-medium transition-all duration-200 disabled:opacity-50"
                  >
                    {isBatchProcessing ? (
                      <>
                        <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                        Processing...
                      </>
                    ) : (
                      <>
                        <Play className="h-4 w-4 mr-2" />
                        Process Selected ({selectedDocuments.size})
                      </>
                    )}
                  </Button>
                </div>
              </div>
            )}

            {/* Batch Progress Display */}
            {batchProgress && (
              <div className="mb-6 p-4 bg-blue-50 rounded-xl border border-blue-200">
                <div className="flex items-center justify-between mb-3">
                  <h5 className="font-semibold text-blue-900">Batch Processing Progress</h5>
                  <span className="text-sm text-blue-700">
                    {batchProgress.completed_documents} of {batchProgress.total_documents} completed
                  </span>
                </div>
                <div className="w-full bg-blue-200 rounded-full h-2 mb-3">
                  <div 
                    className="bg-blue-600 h-2 rounded-full transition-all duration-500"
                    style={{ width: `${batchProgress.overall_progress_percent}%` }}
                  />
                </div>
                <div className="text-xs text-blue-700">
                  Status: {batchProgress.status} | Progress: {batchProgress.overall_progress_percent.toFixed(1)}%
                </div>
                {batchProgress.message && (
                  <div className="mt-2 text-sm text-blue-800 font-medium">
                    {batchProgress.message}
                  </div>
                )}
                {batchProgress.current_processing.length > 0 && (
                  <div className="mt-2 text-xs text-blue-600">
                    Currently processing: {batchProgress.current_processing.map(p => `${p.ticker} (${p.stage})`).join(', ')}
                  </div>
                )}
              </div>
            )}

            {/* Batch Error Display */}
            {batchError && (
              <div className="mb-6 p-4 bg-red-50 rounded-xl border border-red-200">
                <div className="flex items-center justify-between">
                  <h5 className="font-semibold text-red-900">Batch Processing Error</h5>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => setBatchError(null)}
                    className="text-red-600 hover:text-red-700"
                  >
                    ×
                  </Button>
                </div>
                <p className="text-sm text-red-700 mt-2">{batchError}</p>
              </div>
            )}

            <div className="space-y-4 max-h-96 overflow-y-auto">
              {searchResults.map((doc, index) => (
                <div key={index} className="p-5 border border-gray-200 rounded-xl bg-gradient-to-r from-gray-50 to-white hover:from-microsoft-purple/5 hover:to-purple-50 transition-all duration-200 hover:shadow-md">
                  <div className="flex items-start justify-between">
                    <div className="flex items-start space-x-3">
                      {/* Checkbox for batch selection - Only for company search */}
                      {searchFilters.searchType === 'company' && (
                        <Checkbox
                          id={`doc-${doc.id}`}
                          checked={selectedDocuments.has(doc.id)}
                          onCheckedChange={() => toggleDocumentSelection(doc.id)}
                          className="mt-1"
                        />
                      )}
                      <div className="flex-1">
                        <div className="flex items-center space-x-3 mb-3">
                          <div className="w-8 h-8 bg-microsoft-purple/10 rounded-lg flex items-center justify-center">
                            <FileText className="h-4 w-4 text-microsoft-purple" />
                          </div>
                          <div>
                            <span className="font-semibold text-microsoft-gray text-lg">{doc.company}</span>
                            <span className="ml-2 px-2 py-1 bg-microsoft-purple/10 text-microsoft-purple text-xs font-medium rounded-full">
                              {doc.document_type}
                            </span>
                          </div>
                        </div>
                        <p className="text-gray-700 mb-3 font-medium">{doc.title}</p>
                        <div className="flex items-center space-x-6 text-sm text-gray-600">
                          <span className="flex items-center">
                            <Calendar className="h-4 w-4 mr-2 text-microsoft-purple" />
                            Filed: {doc.filing_date}
                          </span>
                          <span className="flex items-center">
                            <Building2 className="h-4 w-4 mr-2 text-microsoft-purple" />
                            CIK: {doc.cik}
                          </span>
                        </div>
                      </div>
                    </div>
                    <div className="flex flex-col space-y-2 ml-4">
                      <Button
                        variant="outline"
                        size="sm"
                        className="text-xs px-3 py-1 h-8"
                        onClick={() => handleProcessDocument(doc)}
                      >
                        <Download className="h-3 w-3 mr-1" />
                        Process
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="text-xs px-3 py-1 h-8"
                        onClick={() => handleViewDocument(doc)}
                      >
                        <ExternalLink className="h-3 w-3 mr-1" />
                        View
                      </Button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </Card>
  );
}
