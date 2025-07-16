"""
Document Upload API endpoints for RAG document processing.
"""
import asyncio
import logging
import os
import tempfile
import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile, File, Form, BackgroundTasks, Depends
from fastapi.responses import JSONResponse

from ..core.config import Settings
from ..models.schemas import (
    DocumentUploadBatchRequest, 
    DocumentUploadBatchResponse,
    DocumentProcessingStatus,
    ProcessingResult,
    BatchProcessingStatus
)
from ..services.document_intelligence_service import DocumentIntelligenceService

logger = logging.getLogger(__name__)

router = APIRouter()

# Global service instance
document_service: Optional[DocumentIntelligenceService] = None

def get_document_service():
    """Get or create document intelligence service instance."""
    global document_service
    if document_service is None:
        settings = Settings()
        document_service = DocumentIntelligenceService(settings)
    return document_service

@router.post("/upload", response_model=DocumentUploadBatchResponse)
async def upload_documents(
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...),
    batch_processing: bool = Form(True),
    service: DocumentIntelligenceService = Depends(get_document_service)
):
    """
    Upload and process multiple documents.
    Supports PDF and HTML files.
    """
    try:
        # Validate file types
        supported_types = ["application/pdf", "text/html", "application/msword", 
                          "application/vnd.openxmlformats-officedocument.wordprocessingml.document"]
        
        uploaded_files = []
        file_paths = []
        
        for file in files:
            # Validate file type
            if file.content_type not in supported_types:
                raise HTTPException(
                    status_code=400,
                    detail=f"Unsupported file type: {file.content_type}. Supported types: PDF, HTML, Word documents"
                )
            
            # Validate file size (50MB limit)
            file_content = await file.read()
            if len(file_content) > 50 * 1024 * 1024:  # 50MB
                raise HTTPException(
                    status_code=400,
                    detail=f"File {file.filename} is too large. Maximum size is 50MB"
                )
            
            # Save file temporarily
            temp_dir = tempfile.gettempdir()
            temp_file_path = os.path.join(temp_dir, f"{uuid.uuid4()}_{file.filename}")
            
            with open(temp_file_path, "wb") as temp_file:
                temp_file.write(file_content)
            
            uploaded_files.append(file.filename)
            file_paths.append(temp_file_path)
        
        logger.info(f"Uploaded {len(uploaded_files)} files for processing")
        
        if batch_processing:
            # Process in batch
            batch_status = await service.process_batch(file_paths, uploaded_files)
            
            # Clean up temporary files
            for file_path in file_paths:
                try:
                    os.unlink(file_path)
                except Exception as e:
                    logger.warning(f"Failed to cleanup temp file {file_path}: {e}")
            
            return DocumentUploadBatchResponse(
                processing_ids=[result.processing_id for result in batch_status.results],
                batch_id=batch_status.batch_id,
                message=f"Batch processing started for {len(uploaded_files)} documents"
            )
        else:
            # Process individually
            processing_ids = []
            for file_path, filename in zip(file_paths, uploaded_files):
                result = await service.process_document(file_path, filename)
                processing_ids.append(result.processing_id)
            
            # Clean up temporary files
            for file_path in file_paths:
                try:
                    os.unlink(file_path)
                except Exception as e:
                    logger.warning(f"Failed to cleanup temp file {file_path}: {e}")
            
            return DocumentUploadBatchResponse(
                processing_ids=processing_ids,
                message=f"Processing started for {len(uploaded_files)} documents"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading documents: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.get("/status/{processing_id}", response_model=DocumentProcessingStatus)
async def get_processing_status(
    processing_id: str,
    service: DocumentIntelligenceService = Depends(get_document_service)
):
    """Get processing status for a specific document."""
    try:
        status = service.get_processing_status(processing_id)
        if not status:
            raise HTTPException(status_code=404, detail="Processing ID not found")
        return status
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting processing status: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.get("/batch-status/{batch_id}", response_model=BatchProcessingStatus)
async def get_batch_status(
    batch_id: str,
    service: DocumentIntelligenceService = Depends(get_document_service)
):
    """Get batch processing status."""
    try:
        status = service.get_batch_status(batch_id)
        if not status:
            raise HTTPException(status_code=404, detail="Batch ID not found")
        return status
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting batch status: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.get("/all-status", response_model=List[DocumentProcessingStatus])
async def get_all_processing_status(
    service: DocumentIntelligenceService = Depends(get_document_service)
):
    """Get all processing statuses."""
    try:
        return service.get_all_processing_status()
    except Exception as e:
        logger.error(f"Error getting all processing statuses: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.get("/all-batch-status", response_model=List[BatchProcessingStatus])
async def get_all_batch_status(
    service: DocumentIntelligenceService = Depends(get_document_service)
):
    """Get all batch processing statuses."""
    try:
        return service.get_all_batch_status()
    except Exception as e:
        logger.error(f"Error getting all batch statuses: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.delete("/cleanup")
async def cleanup_old_status(
    max_age_hours: int = 24,
    service: DocumentIntelligenceService = Depends(get_document_service)
):
    """Clean up old processing statuses."""
    try:
        service.cleanup_old_status(max_age_hours)
        return {"message": f"Cleaned up processing statuses older than {max_age_hours} hours"}
    except Exception as e:
        logger.error(f"Error cleaning up old statuses: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.post("/test-document-intelligence")
async def test_document_intelligence(
    file: UploadFile = File(...),
    service: DocumentIntelligenceService = Depends(get_document_service)
):
    """Test Document Intelligence API with a single file."""
    try:
        # Validate file type
        if file.content_type not in ["application/pdf", "text/html"]:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file type: {file.content_type}. Supported types: PDF, HTML"
            )
        
        # Save file temporarily
        file_content = await file.read()
        temp_dir = tempfile.gettempdir()
        temp_file_path = os.path.join(temp_dir, f"{uuid.uuid4()}_{file.filename}")
        
        with open(temp_file_path, "wb") as temp_file:
            temp_file.write(file_content)
        
        try:
            # Extract markdown
            markdown_content = await service._extract_markdown(temp_file_path)
            
            # Create chunks
            chunks = await service._create_chunks(markdown_content, file.filename)
            
            # Clean up temp file
            os.unlink(temp_file_path)
            
            return {
                "filename": file.filename,
                "content_length": len(markdown_content),
                "chunks_created": len(chunks),
                "sample_content": markdown_content[:500] + "..." if len(markdown_content) > 500 else markdown_content,
                "sample_chunks": [
                    {
                        "content": chunk.page_content[:200] + "..." if len(chunk.page_content) > 200 else chunk.page_content,
                        "metadata": chunk.metadata
                    }
                    for chunk in chunks[:3]  # Show first 3 chunks
                ]
            }
        
        except Exception as e:
            # Clean up temp file on error
            if os.path.exists(temp_file_path):
                os.unlink(temp_file_path)
            raise e
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error testing document intelligence: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
