"""
Document Intelligence Service for RAG document processing.
Uses Azure Document Intelligence API with Langchain integration.
"""
import asyncio
import logging
from typing import List, Dict, Any, Optional, Union
from pathlib import Path
import tempfile
import os
from datetime import datetime, timedelta
import uuid

from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.ai.documentintelligence.models import AnalyzeDocumentRequest, DocumentContentFormat
from azure.core.credentials import AzureKeyCredential
from langchain.schema import Document
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import AzureSearch
from langchain_openai import AzureOpenAIEmbeddings

from ..core.config import Settings
from ..models.schemas import DocumentProcessingStatus, ProcessingResult, BatchProcessingStatus

logger = logging.getLogger(__name__)

class DocumentIntelligenceService:
    """Service for processing documents using Azure Document Intelligence."""
    
    def __init__(self, settings: Settings):
        self.settings = settings
        self.client = DocumentIntelligenceClient(
            endpoint=settings.document_intel_account_url,
            credential=AzureKeyCredential(settings.document_intel_key)
        )
        
        # Initialize embeddings for vector search
        self.embeddings = AzureOpenAIEmbeddings(
            azure_deployment=settings.openai_embed_deployment,
            azure_endpoint=settings.openai_endpoint,
            api_key=settings.openai_key,
            api_version=settings.openai_api_version
        )
        
        # Initialize text splitter
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=settings.chunk_size,
            chunk_overlap=settings.chunk_overlap,
            length_function=len,
            separators=["\n\n", "\n", " ", ""]
        )
        
        # Processing status tracking
        self.processing_status: Dict[str, DocumentProcessingStatus] = {}
        self.batch_status: Dict[str, BatchProcessingStatus] = {}
        
    async def process_document(self, file_path: str, filename: str) -> ProcessingResult:
        """Process a single document through Document Intelligence."""
        processing_id = str(uuid.uuid4())
        
        try:
            # Update status
            self.processing_status[processing_id] = DocumentProcessingStatus(
                id=processing_id,
                filename=filename,
                status="processing",
                progress=0,
                started_at=datetime.utcnow(),
                message="Starting document analysis..."
            )
            
            logger.info(f"Processing document: {filename}")
            
            # Step 1: Extract markdown using Document Intelligence
            self._update_status(processing_id, "extracting", 20, "Extracting content with Document Intelligence...")
            markdown_content = await self._extract_markdown(file_path)
            
            # Step 2: Create document chunks
            self._update_status(processing_id, "chunking", 40, "Creating document chunks...")
            chunks = await self._create_chunks(markdown_content, filename)
            
            # Step 3: Generate embeddings and store in vector search
            self._update_status(processing_id, "embedding", 60, "Generating embeddings...")
            await self._store_in_vector_search(chunks)
            
            # Step 4: Complete processing
            self._update_status(processing_id, "completed", 100, f"Successfully processed {len(chunks)} chunks")
            
            result = ProcessingResult(
                processing_id=processing_id,
                filename=filename,
                status="completed",
                chunks_created=len(chunks),
                characters_processed=len(markdown_content),
                processing_time_seconds=(datetime.utcnow() - self.processing_status[processing_id].started_at).total_seconds()
            )
            
            logger.info(f"Document processing completed: {filename} - {len(chunks)} chunks created")
            return result
            
        except Exception as e:
            logger.error(f"Error processing document {filename}: {str(e)}")
            self._update_status(processing_id, "failed", 0, f"Error: {str(e)}")
            return ProcessingResult(
                processing_id=processing_id,
                filename=filename,
                status="failed",
                error=str(e),
                processing_time_seconds=(datetime.utcnow() - self.processing_status[processing_id].started_at).total_seconds()
            )
    
    async def process_batch(self, file_paths: List[str], filenames: List[str]) -> BatchProcessingStatus:
        """Process multiple documents in batch."""
        batch_id = str(uuid.uuid4())
        
        logger.info(f"Starting batch processing of {len(file_paths)} documents")
        
        # Initialize batch status
        batch_status = BatchProcessingStatus(
            batch_id=batch_id,
            total_documents=len(file_paths),
            status="processing",
            started_at=datetime.utcnow()
        )
        self.batch_status[batch_id] = batch_status
        
        # Process documents concurrently
        tasks = [
            self.process_document(file_path, filename)
            for file_path, filename in zip(file_paths, filenames)
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Handle exceptions and update batch status
        processed_results = []
        completed_count = 0
        failed_count = 0
        
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Exception in batch processing {filenames[i]}: {str(result)}")
                failed_result = ProcessingResult(
                    processing_id=str(uuid.uuid4()),
                    filename=filenames[i],
                    status="failed",
                    error=str(result)
                )
                processed_results.append(failed_result)
                failed_count += 1
            else:
                processed_results.append(result)
                if result.status == "completed":
                    completed_count += 1
                else:
                    failed_count += 1
        
        # Update final batch status
        batch_status.completed_documents = completed_count
        batch_status.failed_documents = failed_count
        batch_status.processing_documents = 0
        batch_status.status = "completed"
        batch_status.completed_at = datetime.utcnow()
        batch_status.results = processed_results
        batch_status.updated_at = datetime.utcnow()
        
        logger.info(f"Batch processing completed: {completed_count} succeeded, {failed_count} failed")
        
        return batch_status
    
    async def _extract_markdown(self, file_path: str) -> str:
        """Extract markdown content from document using Document Intelligence."""
        try:
            with open(file_path, "rb") as f:
                file_content = f.read()
            
            # Analyze document with prebuilt layout model
            poller = self.client.begin_analyze_document(
                "prebuilt-layout",
                analyze_request=AnalyzeDocumentRequest(bytes_source=file_content),
                output_content_format=DocumentContentFormat.MARKDOWN
            )
            
            result = poller.result()
            
            # Extract markdown content
            if result.content:
                return result.content
            else:
                logger.warning(f"No content extracted from document: {file_path}")
                return ""
                
        except Exception as e:
            logger.error(f"Error extracting markdown from {file_path}: {str(e)}")
            raise
    
    async def _create_chunks(self, markdown_content: str, filename: str) -> List[Document]:
        """Create document chunks with metadata."""
        try:
            # Split text into chunks
            chunks = self.text_splitter.split_text(markdown_content)
            
            # Create Document objects with metadata
            documents = []
            for i, chunk in enumerate(chunks):
                if len(chunk.strip()) > 0:  # Skip empty chunks
                    doc = Document(
                        page_content=chunk,
                        metadata={
                            "filename": filename,
                            "chunk_index": i,
                            "total_chunks": len(chunks),
                            "document_type": "uploaded_document",
                            "processed_at": datetime.utcnow().isoformat(),
                            "source": "document_upload"
                        }
                    )
                    documents.append(doc)
            
            return documents
            
        except Exception as e:
            logger.error(f"Error creating chunks for {filename}: {str(e)}")
            raise
    
    async def _store_in_vector_search(self, documents: List[Document]) -> None:
        """Store document chunks in Azure AI Search vector store."""
        try:
            # Initialize Azure Search vector store
            vector_store = AzureSearch(
                azure_search_endpoint=self.settings.search_endpoint,
                azure_search_key=self.settings.search_admin_key,
                index_name=self.settings.search_index_upload,
                embedding_function=self.embeddings.embed_query,
                fields=[
                    {
                        "name": "content",
                        "type": "Edm.String",
                        "searchable": True,
                        "retrievable": True,
                    },
                    {
                        "name": "metadata",
                        "type": "Edm.String",
                        "searchable": True,
                        "retrievable": True,
                    },
                    {
                        "name": "content_vector",
                        "type": "Collection(Edm.Single)",
                        "searchable": True,
                        "retrievable": True,
                        "dimensions": 1536,  # text-embedding-3-small dimensions
                        "vectorSearchConfiguration": "default"
                    }
                ]
            )
            
            # Add documents to vector store
            await vector_store.aadd_documents(documents)
            
            logger.info(f"Successfully stored {len(documents)} documents in vector search")
            
        except Exception as e:
            logger.error(f"Error storing documents in vector search: {str(e)}")
            raise
    
    def _update_status(self, processing_id: str, status: str, progress: int, message: str) -> None:
        """Update processing status."""
        if processing_id in self.processing_status:
            self.processing_status[processing_id].status = status
            self.processing_status[processing_id].progress = progress
            self.processing_status[processing_id].message = message
            self.processing_status[processing_id].updated_at = datetime.utcnow()
    
    def get_processing_status(self, processing_id: str) -> Optional[DocumentProcessingStatus]:
        """Get processing status by ID."""
        return self.processing_status.get(processing_id)
    
    def get_batch_status(self, batch_id: str) -> Optional[BatchProcessingStatus]:
        """Get batch processing status by ID."""
        return self.batch_status.get(batch_id)
    
    def get_all_processing_status(self) -> List[DocumentProcessingStatus]:
        """Get all processing statuses."""
        return list(self.processing_status.values())
    
    def get_all_batch_status(self) -> List[BatchProcessingStatus]:
        """Get all batch processing statuses."""
        return list(self.batch_status.values())
    
    def cleanup_old_status(self, max_age_hours: int = 24) -> None:
        """Clean up old processing statuses."""
        cutoff_time = datetime.utcnow() - timedelta(hours=max_age_hours)
        
        # Clean up individual processing statuses
        to_remove = [
            pid for pid, status in self.processing_status.items()
            if status.updated_at < cutoff_time
        ]
        
        for pid in to_remove:
            del self.processing_status[pid]
        
        # Clean up batch statuses
        batch_to_remove = [
            bid for bid, status in self.batch_status.items()
            if status.updated_at < cutoff_time
        ]
        
        for bid in batch_to_remove:
            del self.batch_status[bid]
        
        logger.info(f"Cleaned up {len(to_remove)} old processing statuses and {len(batch_to_remove)} old batch statuses")
