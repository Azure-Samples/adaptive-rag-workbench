import React from 'react';
import { DocumentUpload } from '@/components/DocumentUpload';

const DocumentUploadPage: React.FC = () => {
  return (
    <div className="container mx-auto px-4 py-8">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-gray-900 mb-2">
          Document Upload
        </h1>
        <p className="text-gray-600">
          Upload and process documents for your RAG knowledge base. 
          Supports PDF, HTML, and Word documents with automatic text extraction and chunking.
        </p>
      </div>
      
      <DocumentUpload />
    </div>
  );
};

export default DocumentUploadPage;
