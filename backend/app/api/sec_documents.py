from fastapi import APIRouter, HTTPException, Depends, Query
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
import logging
import asyncio
import time
import traceback
from datetime import datetime, timedelta

from app.services.sec_document_service import SECDocumentService, SECDocumentInfo
from app.services.azure_services import AzureServiceManager
from app.models.schemas import (
    ProcessDocumentRequest, ProcessDocumentResponse, 
    ProcessMultipleDocumentsRequest, ProcessMultipleDocumentsResponse,
    SECFilingsRequest, SECDocumentLibraryResponse, SECAnalyticsResponse,
    ChunkVisualizationResponse, DocumentProcessingProgress, ProcessingStage,
    BatchProcessingStatus
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/sec", tags=["SEC Documents"])

class CompanySearchRequest(BaseModel):
    query: str

class CompanySearchResponse(BaseModel):
    companies: List[Dict[str, Any]]

class FilingRequest(BaseModel):
    ticker: str
    form_types: Optional[List[str]] = ["10-K", "10-Q", "8-K"]
    limit: Optional[int] = 20

class SpecificFilingRequest(BaseModel):
    ticker: str
    form_types: List[str]  # Multiple form types
    years: Optional[List[int]] = None  # Changed from single year to multiple years
    limit: Optional[int] = 10

# Global dictionary to track batch processing status
batch_processing_status: Dict[str, BatchProcessingStatus] = {}

async def get_sec_service() -> SECDocumentService:
    """Dependency to get SEC document service"""
    try:
        # For basic SEC operations (search, filings), we don't need Azure services
        # Only initialize Azure manager if actually needed for document processing
        azure_manager = None
        try:
            from app.core.config import settings
            azure_manager = AzureServiceManager()
            await azure_manager.initialize()
            logger.info("✅ Azure services initialized successfully for SEC service")
        except Exception as azure_error:
            logger.warning(f"⚠️ Azure services not available: {azure_error}")
            logger.info("SEC service will work without Azure integration (search and basic operations only)")
            logger.info("📝 Note: Document processing (indexing) requires Azure services to be configured")
        
        service = SECDocumentService(azure_manager)
        logger.info(f"🔧 SEC service created with Azure manager: {'✅ Available' if azure_manager else '❌ Not available'}")
        return service
    except Exception as e:
        logger.error(f"💥 Failed to initialize SEC service: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to initialize SEC service: {str(e)}")

@router.post("/companies/search", response_model=CompanySearchResponse)
async def search_companies(
    request: CompanySearchRequest,
    sec_service: SECDocumentService = Depends(get_sec_service)
):
    """
    Search for companies by name or ticker symbol
    """
    try:
        # async with observability.trace_operation("sec_company_search") as span:
        #     span.set_attribute("query", request.query)
        
        companies = await sec_service.search_companies(request.query)
        
        #     span.set_attribute("companies_found", len(companies))
        #     span.set_attribute("success", True)
        
        return CompanySearchResponse(companies=companies)
        
    except Exception as e:
        logger.error(f"Error searching companies: {e}")
        # observability.record_error("sec_company_search_error", str(e))
        raise HTTPException(status_code=500, detail=f"Failed to search companies: {str(e)}")

@router.post("/filings")
async def get_company_filings(
    request: FilingRequest,
    sec_service: SECDocumentService = Depends(get_sec_service)
):
    """    Get recent filings for a company
    """
    try:
        # async with observability.trace_operation("sec_get_filings") as span:
        #     span.set_attribute("ticker", request.ticker)
        #     span.set_attribute("form_types", str(request.form_types))
        
        filings = await sec_service.get_company_filings(
            ticker=request.ticker,
            form_types=request.form_types,
            limit=request.limit
        )
        
        # Convert to dict format for JSON response
        filings_data = []
        for filing in filings:
            filing_dict = {
                "ticker": filing.ticker,
                "company_name": filing.company_name,
                "cik": filing.cik,
                "form_type": filing.form_type,
                "filing_date": filing.filing_date.isoformat(),
                "period_end_date": filing.period_end_date.isoformat() if filing.period_end_date else None,
                "document_url": filing.document_url,
                "accession_number": filing.accession_number,
                "file_size": filing.file_size
            }
            filings_data.append(filing_dict)
        
        #     span.set_attribute("filings_found", len(filings_data))
        #     span.set_attribute("success", True)
        
        return {
            "ticker": request.ticker,
            "filings": filings_data,
            "total_count": len(filings_data)
        }
        
    except Exception as e:
        logger.error(f"Error getting filings for {request.ticker}: {e}")
        # observability.record_error("sec_get_filings_error", str(e))
        raise HTTPException(status_code=500, detail=f"Failed to get filings: {str(e)}")

@router.post("/documents/process", response_model=ProcessDocumentResponse)
async def process_sec_document(
    request: ProcessDocumentRequest,
    sec_service: SECDocumentService = Depends(get_sec_service)
):
    """
    Retrieve and process a SEC document for the knowledge base
    """
    try:
        # Check if Azure services are available before processing
        if not sec_service.azure_manager:
            logger.error("❌ Azure services not available - cannot process document for indexing")
            raise HTTPException(
                status_code=503, 
                detail="Azure services are not configured. Document processing requires Azure AI Search and other Azure services to be available."
            )
        
        result = await sec_service.retrieve_and_process_document(
            ticker=request.ticker,
            accession_number=request.accession_number,
            document_id=request.document_id
        )
        
        return ProcessDocumentResponse(**result)
            
    except Exception as e:
        logger.error(f"Error processing SEC document: {e}")
        # observability.record_error("sec_process_document_error", str(e))
        raise HTTPException(status_code=500, detail=f"Failed to process document: {str(e)}")

@router.post("/documents/process-multiple", response_model=ProcessMultipleDocumentsResponse)
async def process_multiple_sec_documents(
    request: ProcessMultipleDocumentsRequest,
    sec_service: SECDocumentService = Depends(get_sec_service)
):    
    """
    Retrieve and process multiple SEC documents for the knowledge base with parallel processing
    """
    start_time = time.time()
    batch_id = request.batch_id or f"batch_{int(time.time())}"
    
    try:
        logger.info(f"Starting parallel processing of {len(request.filings)} SEC documents (batch: {batch_id})")
        
        # Check if Azure services are available before starting batch processing
        if not sec_service.azure_manager:
            logger.error("❌ Azure services not available - cannot process documents for indexing")
            raise HTTPException(
                status_code=503, 
                detail="Azure services are not configured. Document processing requires Azure AI Search and other Azure services to be available."
            )
        
        logger.info(f"✅ Azure services are available - proceeding with batch processing")
        
        # Initialize batch status tracking
        batch_status = BatchProcessingStatus(
            batch_id=batch_id,
            total_documents=len(request.filings),
            completed_documents=0,
            failed_documents=0,
            current_processing=[],
            overall_progress_percent=0.0,
            started_at=datetime.now(),
            status="queued"  # Start as queued, will change to processing when first document starts
        )
        batch_processing_status[batch_id] = batch_status
        
        # Progress tracking callback
        async def update_batch_progress(progress: DocumentProcessingProgress):
            # Update current processing list
            current_processing = [p for p in batch_status.current_processing 
                                 if p.document_id != progress.document_id]
            if progress.stage != ProcessingStage.COMPLETED and progress.stage != ProcessingStage.FAILED:
                current_processing.append(progress)
            batch_status.current_processing = current_processing
            
            # Update batch status to "processing" when first document starts
            if progress.stage == ProcessingStage.DOWNLOADING and batch_status.status != "processing":
                batch_status.status = "processing"
                logger.info(f"🔄 Batch {batch_id}: Status updated to PROCESSING - first document started")
            elif progress.stage != ProcessingStage.QUEUED and batch_status.status == "processing":
                logger.debug(f"Batch {batch_id}: Document {progress.document_id} -> {progress.stage.value} ({progress.progress_percent:.1f}%) - {progress.message}")
            
            # Update completion counts
            if progress.stage == ProcessingStage.COMPLETED:
                batch_status.completed_documents += 1
                logger.info(f"Batch {batch_id}: Document {progress.document_id} completed! ({batch_status.completed_documents}/{batch_status.total_documents})")
            elif progress.stage == ProcessingStage.FAILED:
                batch_status.failed_documents += 1
                logger.info(f"Batch {batch_id}: Document {progress.document_id} failed! ({batch_status.failed_documents} failures)")
            
            # Calculate overall progress
            completed_or_failed = batch_status.completed_documents + batch_status.failed_documents
            batch_status.overall_progress_percent = (completed_or_failed / batch_status.total_documents * 100.0)
            
            # Add individual document progress to overall calculation
            if len(current_processing) > 0:
                # Add partial progress from currently processing documents
                partial_progress = sum(p.progress_percent / 100.0 for p in current_processing) / batch_status.total_documents * 100.0
                batch_status.overall_progress_percent = min(100.0, batch_status.overall_progress_percent + partial_progress)
            
            logger.debug(f"Batch {batch_id} progress: {batch_status.overall_progress_percent:.1f}% - {len(current_processing)} processing, {batch_status.completed_documents} completed, {batch_status.failed_documents} failed")
        
        # Create semaphore for controlling parallel processing
        max_parallel = min(request.max_parallel, len(request.filings))
        semaphore = asyncio.Semaphore(max_parallel)
        
        async def process_with_semaphore(filing_request):
            # Create initial progress when document is picked up
            document_id = f"{filing_request.ticker}_{filing_request.accession_number}"
            initial_progress = DocumentProcessingProgress(
                document_id=document_id,
                ticker=filing_request.ticker,
                accession_number=filing_request.accession_number,
                stage=ProcessingStage.QUEUED,
                progress_percent=0.0,
                message="Starting processing...",
                started_at=datetime.now(),
                updated_at=datetime.now()
            )
            await update_batch_progress(initial_progress)
            
            async with semaphore:
                # Update to indicate actually starting processing
                initial_progress.stage = ProcessingStage.DOWNLOADING
                initial_progress.message = "Acquired processing slot, starting download..."
                initial_progress.progress_percent = 5.0
                await update_batch_progress(initial_progress)
                
                return await process_single_document_with_progress(
                    filing_request, sec_service, batch_id, update_batch_progress
                )
        
        # Process documents in parallel
        logger.info(f"Processing {len(request.filings)} documents with max {max_parallel} parallel threads")
        tasks = [process_with_semaphore(filing) for filing in request.filings]
        
        # Start processing in background without waiting for completion
        async def background_processing():
            """Run the actual processing in background"""
            try:
                logger.info(f"🚀 Starting background processing for batch {batch_id} with {len(tasks)} tasks")
                
                # Check if Azure services are available before processing
                if not sec_service.azure_manager:
                    raise Exception("Azure services are not available. Cannot process documents for indexing.")
                
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                # Process results
                total_chunks = 0
                total_tokens = 0
                processed_count = 0
                skipped_count = 0
                failed_count = 0
                
                for i, result in enumerate(results):
                    if isinstance(result, Exception):
                        logger.error(f"Document processing failed: {result}")
                        failed_count += 1
                    else:
                        if result.skipped:
                            skipped_count += 1
                        else:
                            processed_count += 1
                            total_chunks += result.chunks_created
                            total_tokens += result.tokens_used or 0
                
                processing_time = time.time() - start_time
                
                # Update final batch status
                batch_status.completed_documents = processed_count + skipped_count
                batch_status.failed_documents = failed_count
                batch_status.overall_progress_percent = 100.0
                batch_status.current_processing = []
                batch_status.finished_at = datetime.now()
                batch_status.status = "completed" if failed_count == 0 else "completed_with_errors"
                
                logger.info(f"🎉 Background processing completed: {processed_count} processed, {skipped_count} skipped, {failed_count} failed in {processing_time:.2f}s")
                logger.info(f"📊 Total chunks created: {total_chunks}, Total tokens used: {total_tokens}")
                
            except Exception as e:
                logger.error(f"💥 Error in background processing: {e}")
                logger.error(f"Full traceback: {traceback.format_exc()}")
                # Update batch status with error
                batch_status.status = "failed"
                batch_status.finished_at = datetime.now()
                batch_status.error_message = str(e)
        
        # Start background processing task without waiting
        asyncio.create_task(background_processing())
        
        # Return immediately with batch_id so frontend can start polling
        logger.info(f"✅ Batch {batch_id} started in background, returning batch_id for polling")
        return ProcessMultipleDocumentsResponse(
            batch_id=batch_id,
            results=[],  # Empty for now, client should poll for results
            summary={
                "total_requested": len(request.filings),
                "processed": 0,  # Will be updated via polling
                "skipped": 0,
                "failed": 0,
                "processing_time_seconds": 0.0,
                "parallel_threads_used": max_parallel,
                "status": "processing_started"
            },
            processing_time_seconds=0.0,
            total_chunks_created=0,
            total_tokens_used=0
        )
        
    except Exception as e:
        logger.error(f"Error in parallel processing: {e}")
        # Update batch status with error instead of deleting
        if batch_id in batch_processing_status:
            batch_processing_status[batch_id].status = "failed"
            batch_processing_status[batch_id].finished_at = datetime.now()
            batch_processing_status[batch_id].error_message = str(e)
        raise HTTPException(status_code=500, detail=f"Failed to process documents: {str(e)}")

# Add new endpoint for progress tracking
@router.get("/batch/{batch_id}/status", response_model=BatchProcessingStatus)
async def get_batch_processing_status(batch_id: str):
    """Get the current status of a batch processing operation"""
    if batch_id not in batch_processing_status:
        raise HTTPException(status_code=404, detail="Batch not found")
    return batch_processing_status[batch_id]

@router.get("/batches", response_model=List[BatchProcessingStatus])
async def list_batch_statuses():
    """List all batch processing statuses"""
    return list(batch_processing_status.values())

@router.delete("/batch/{batch_id}")
async def delete_batch_status(batch_id: str):
    """Delete a batch processing status (for cleanup)"""
    if batch_id not in batch_processing_status:
        raise HTTPException(status_code=404, detail="Batch not found")
    del batch_processing_status[batch_id]
    return {"message": f"Batch {batch_id} status deleted"}

@router.post("/batches/cleanup")
async def cleanup_old_batches(older_than_hours: int = 24):
    """Clean up batch statuses older than specified hours"""
    cutoff_time = datetime.now() - timedelta(hours=older_than_hours)
    
    deleted_count = 0
    batch_ids_to_delete = []
    
    for batch_id, status in batch_processing_status.items():
        if (status.finished_at and status.finished_at < cutoff_time) or \
           (not status.finished_at and status.started_at < cutoff_time):
            batch_ids_to_delete.append(batch_id)
    
    for batch_id in batch_ids_to_delete:
        del batch_processing_status[batch_id]
        deleted_count += 1
    
    return {"deleted_count": deleted_count, "deleted_batches": batch_ids_to_delete}

@router.get("/health")
async def health_check():
    """
    Health check for SEC document service
    """
    try:
        # Basic health check - could expand to test EDGAR API connectivity
        return {
            "status": "healthy",
            "service": "SEC Document Service",
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"SEC service health check failed: {e}")
        raise HTTPException(status_code=503, detail="SEC service unhealthy")

@router.get("/azure-status")
async def check_azure_status(
    sec_service: SECDocumentService = Depends(get_sec_service)
):
    """
    Check Azure services status for document processing
    """
    try:
        if not sec_service.azure_manager:
            return {
                "azure_available": False,
                "status": "unavailable",
                "message": "Azure services are not configured or failed to initialize",
                "capabilities": {
                    "document_search": True,  # SEC filings search works without Azure
                    "document_processing": False,  # Document indexing requires Azure
                    "vector_search": False,
                    "embeddings": False
                }
            }
        
        # Test Azure services
        try:
            # Try a simple operation to verify Azure services work
            # You could add more specific tests here
            services_status = {
                "search_client": sec_service.azure_manager.search_client is not None,
                "embedding_client": sec_service.azure_manager.embedding_client is not None,
                "openai_client": sec_service.azure_manager.openai_client is not None,
            }
            
            all_services_available = all(services_status.values())
            
            return {
                "azure_available": all_services_available,
                "status": "available" if all_services_available else "partial",
                "message": "Azure services are properly configured" if all_services_available else "Some Azure services are missing",
                "services": services_status,
                "capabilities": {
                    "document_search": True,
                    "document_processing": all_services_available,
                    "vector_search": services_status.get("search_client", False),
                    "embeddings": services_status.get("embedding_client", False)
                }
            }
            
        except Exception as azure_test_error:
            logger.error(f"Azure services test failed: {azure_test_error}")
            return {
                "azure_available": False,
                "status": "error",
                "message": f"Azure services test failed: {str(azure_test_error)}",
                "capabilities": {
                    "document_search": True,
                    "document_processing": False,
                    "vector_search": False,
                    "embeddings": False
                }
            }
            
    except Exception as e:
        logger.error(f"Azure status check failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to check Azure status: {str(e)}")

@router.get("/form-types")
async def get_supported_form_types():
    """
    Get list of supported SEC form types
    """
    return {
        "supported_forms": [
            {
                "form_type": "10-K",
                "description": "Annual Report",
                "frequency": "Annual"
            },
            {
                "form_type": "10-Q", 
                "description": "Quarterly Report",
                "frequency": "Quarterly"
            },
            {
                "form_type": "8-K",
                "description": "Current Report", 
                "frequency": "As needed"
            },
            {
                "form_type": "20-F",
                "description": "Foreign Company Annual Report",
                "frequency": "Annual"
            },
            {
                "form_type": "DEF 14A",
                "description": "Proxy Statement",
                "frequency": "Annual"
            }
        ]
    }

@router.post("/filings/specific")
async def get_specific_filings(
    request: SpecificFilingRequest,
    sec_service: SECDocumentService = Depends(get_sec_service)
):
    """
    Get specific filings by form types and years
    """
    try:
        logger.info(f"Getting specific filings for {request.ticker}, forms: {request.form_types}, years: {request.years}")
        
        # Use the new method that handles company name mapping and year filtering better
        filings = await sec_service.get_specific_filings(
            ticker=request.ticker,
            form_types=request.form_types,
            years=request.years,
            limit=request.limit
        )
        
        # Convert to dict format for JSON response
        filings_data = []
        for filing in filings:
            filing_dict = {
                "ticker": filing.ticker,
                "company_name": filing.company_name,
                "cik": filing.cik,
                "form_type": filing.form_type,
                "filing_date": filing.filing_date.isoformat(),
                "period_end_date": filing.period_end_date.isoformat() if filing.period_end_date else None,
                "document_url": filing.document_url,
                "accession_number": filing.accession_number,
                "file_size": filing.file_size,
                "year": filing.filing_date.year
            }
            filings_data.append(filing_dict)
        
        return {
            "ticker": request.ticker,
            "form_types": request.form_types,
            "years": request.years,
            "filings": filings_data,
            "total_count": len(filings_data)
        }
        
    except Exception as e:
        logger.error(f"Error getting specific filings for {request.ticker}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get specific filings: {str(e)}")

@router.get("/analytics", response_model=SECAnalyticsResponse)
async def get_sec_analytics(
    sec_service: SECDocumentService = Depends(get_sec_service)
):
    """
    Get analytics about SEC documents in the vector store
    """
    try:
        logger.info("Getting SEC analytics")
        
        # Get ALL SEC documents from Azure Search using direct search without vector scoring
        # This ensures we get accurate analytics for all documents, not just a sample
        all_results = []
        skip = 0
        batch_size = 1000  # Azure AI Search max per request
        
        while True:
            # Use direct search client to get all documents in batches
            search_results = await sec_service.azure_manager.search_client.search(
                search_text="*",
                select=["id", "content", "document_id", "source", "chunk_id", 
                       "document_type", "company", "filing_date", "section_type", 
                       "page_number", "processed_at", "ticker", "cik", "form_type", 
                       "accession_number", "industry", "document_url", "sic", 
                       "entity_type", "period_end_date", "chunk_index"],
                top=batch_size,
                skip=skip,
                query_type="simple"  # Use simple query for better performance
            )
            
            # Convert async results to list
            batch_results = []
            async for result in search_results:
                batch_results.append(dict(result))
            
            if not batch_results:
                break
                
            all_results.extend(batch_results)
            logger.info(f"Retrieved batch of {len(batch_results)} chunks (total: {len(all_results)})")
            
            # If we got fewer results than batch_size, we've reached the end
            if len(batch_results) < batch_size:
                break
                
            skip += batch_size
        
        logger.info(f"Found {len(all_results)} total chunks for analytics")
        results = all_results
        
        if not results:
            return SECAnalyticsResponse(
                total_documents=0,
                total_chunks=0,
                companies_count=0,
                form_types_distribution={},
                chunks_per_document_avg=0,
                recent_activity=[],
                company_distribution={},
                filing_date_range={}
            )
        
        # Analyze the data
        unique_documents = set()
        form_types_distribution = {}
        companies = {}
        filing_dates = []
        
        for result in results:
            doc_id = result.get('document_id', '')
            if doc_id:
                unique_documents.add(doc_id)
            
            form_type = result.get('form_type', '')
            if form_type:
                form_types_distribution[form_type] = form_types_distribution.get(form_type, 0) + 1
            
            company = result.get('company', '')
            if company:
                companies[company] = companies.get(company, 0) + 1
            
            filing_date = result.get('filing_date', '')
            if filing_date:
                filing_dates.append(filing_date)
        
        # Recent activity (last 10 processed documents)
        recent_results = sorted(
            [r for r in results if r.get('processed_at')],
            key=lambda x: x.get('processed_at', ''),
            reverse=True
        )[:50]  # Get more results to find unique documents
        
        recent_activity = []
        seen_docs = set()
        for result in recent_results:
            doc_id = result.get('document_id', '')
            if doc_id not in seen_docs and len(recent_activity) < 10:
                recent_activity.append({
                    "document_id": doc_id,
                    "company": result.get('company', ''),
                    "form_type": result.get('form_type', ''),
                    "filing_date": result.get('filing_date', ''),
                    "processed_at": result.get('processed_at', ''),
                    "chunk_count": len([r for r in results if r.get('document_id') == doc_id])
                })
                seen_docs.add(doc_id)
        
        # Calculate date range
        filing_date_range = {}
        if filing_dates:
            filing_dates.sort()
            filing_date_range = {
                "earliest": filing_dates[0],
                "latest": filing_dates[-1]
            }
        
        total_documents = len(unique_documents)
        total_chunks = len(results)
        chunks_per_doc_avg = total_chunks / total_documents if total_documents > 0 else 0
        
        logger.info(f"Analytics: {total_documents} docs, {total_chunks} chunks, {len(companies)} companies")
        
        return SECAnalyticsResponse(
            total_documents=total_documents,
            total_chunks=total_chunks,
            companies_count=len(companies),
            form_types_distribution=form_types_distribution,
            chunks_per_document_avg=round(chunks_per_doc_avg, 2),
            recent_activity=recent_activity,
            company_distribution=companies,
            filing_date_range=filing_date_range
        )
        
    except Exception as e:
        logger.error(f"Error getting SEC analytics: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get analytics: {str(e)}")

@router.get("/documents/{document_id}/chunks", response_model=ChunkVisualizationResponse)
async def get_document_chunks(
    document_id: str,
    sec_service: SECDocumentService = Depends(get_sec_service)
):
    """
    Get chunking visualization for a specific SEC document
    """
    try:
        logger.info(f"Getting chunks for document: {document_id}")
        
        # Get all chunks for this document
        results = await sec_service.azure_manager.hybrid_search(
            query="*",
            filters=f"document_id eq '{document_id}'",
            top_k=1000
        )
        
        if not results:
            raise HTTPException(status_code=404, detail="Document not found")
        
        # Get document info from first chunk
        doc_info = {
            "document_id": document_id,
            "company": results[0].get('company', ''),
            "ticker": results[0].get('ticker', ''),
            "form_type": results[0].get('form_type', ''),
            "filing_date": results[0].get('filing_date', ''),
            "accession_number": results[0].get('accession_number', ''),
            "total_chunks": len(results),
            "cik": results[0].get('cik', ''),
            "processed_at": results[0].get('processed_at', '')
        }
        
        # Prepare chunk data
        chunks = []
        total_content_length = 0
        page_numbers = []
        section_types = []
        
        for i, result in enumerate(results):
            content = result.get('content', '')
            total_content_length += len(content)
            
            page_num = result.get('page_number')
            if page_num:
                page_numbers.append(page_num)
            
            section_type = result.get('section_type', '')
            if section_type:
                section_types.append(section_type)
            
            chunks.append({
                "chunk_id": result.get('chunk_id', f"chunk_{i}"),
                "content": content[:200] + "..." if len(content) > 200 else content,
                "content_length": len(content),
                "page_number": page_num,
                "section_type": section_type,
                "credibility_score": result.get('credibility_score', 0),
                "citation_info": result.get('citation_info', ''),
                "search_score": result.get('search_score', 0)
            })
        
        # Calculate chunk statistics
        chunk_stats = {
            "total_chunks": len(chunks),
            "avg_chunk_length": round(total_content_length / len(chunks), 2) if chunks else 0,
            "total_content_length": total_content_length,
            "page_range": {
                "min": min(page_numbers) if page_numbers else None,
                "max": max(page_numbers) if page_numbers else None
            },
            "section_types": list(set(section_types)),
            "avg_credibility_score": round(
                sum(c.get('credibility_score', 0) for c in chunks) / len(chunks), 3
            ) if chunks else 0
        }
        
        return ChunkVisualizationResponse(
            document_id=document_id,
            document_info=doc_info,
            chunks=chunks,
            chunk_stats=chunk_stats
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting document chunks: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get document chunks: {str(e)}")

@router.get("/library", response_model=SECDocumentLibraryResponse)
async def get_sec_document_library(
    company: Optional[str] = None,
    form_type: Optional[str] = None,
    limit: Optional[int] = 100,
    sec_service: SECDocumentService = Depends(get_sec_service)
):
    """
    Get the SEC document library from the vector store.
    First retrieves all unique document_ids, then extracts metadata from a representative chunk,
    then applies company/form_type filters.
    """
    try:
        logger.info(f"Getting SEC document library - company: {company}, form_type: {form_type}")
        
        # Step 1: Get ALL documents from Azure Search (no filters yet)
        # Use a large top_k to get all documents
        all_results = await sec_service.azure_manager.hybrid_search(
            query="*",
            top_k=5000,  # Large number to get all documents
            filters=None  # No filters initially
        )
        
        logger.info(f"Found {len(all_results)} total chunks in index")
        
        # Step 2: Group by document_id and extract metadata from representative chunk
        documents_by_id = {}
        total_chunks = len(all_results)
        
        for result in all_results:
            doc_id = result.get('document_id', '')
            if not doc_id:
                continue
                
            if doc_id not in documents_by_id:
                # Use first chunk as representative for this document
                documents_by_id[doc_id] = {
                    "document_id": doc_id,
                    "company": result.get('company', 'Unknown Company'),
                    "ticker": result.get('ticker', 'N/A'),
                    "form_type": result.get('form_type', 'Unknown'),
                    "filing_date": result.get('filing_date', ''),
                    "accession_number": result.get('accession_number', ''),
                    "chunk_count": 0,
                    "processed_at": result.get('processed_at', ''),
                    "source": result.get('source', ''),
                    "cik": result.get('cik', ''),
                    "industry": result.get('industry', ''),
                    "document_url": result.get('document_url', ''),
                    "section_type": result.get('section_type', '')
                }
            
            # Count chunks for this document
            documents_by_id[doc_id]["chunk_count"] += 1
        
        all_documents = list(documents_by_id.values())
        logger.info(f"Found {len(all_documents)} unique documents before filtering")
        
        # Step 3: Apply filters based on extracted metadata
        filtered_documents = all_documents
        
        if company:
            # Filter by company name (case-insensitive partial match)
            company_lower = company.lower()
            filtered_documents = [
                doc for doc in filtered_documents 
                if company_lower in doc.get("company", "").lower() or 
                   company_lower in doc.get("ticker", "").lower()
            ]
            logger.info(f"After company filter '{company}': {len(filtered_documents)} documents")
        
        if form_type:
            # Filter by form type (exact match)
            filtered_documents = [
                doc for doc in filtered_documents 
                if doc.get("form_type", "").upper() == form_type.upper()
            ]
            logger.info(f"After form_type filter '{form_type}': {len(filtered_documents)} documents")
        
        # Step 4: Apply limit and sort by filing_date (most recent first)
        try:
            # Sort by filing_date, handling empty dates
            filtered_documents = sorted(
                filtered_documents, 
                key=lambda x: x.get("filing_date", "1900-01-01"), 
                reverse=True
            )
        except Exception as e:
            logger.warning(f"Could not sort by filing_date: {e}")
        
        # Apply limit
        limited_documents = filtered_documents[:limit]
        
        # Step 5: Get unique companies and form types for filter dropdowns
        all_companies = list(set(
            doc["company"] for doc in all_documents 
            if doc["company"] and doc["company"] != "Unknown Company"
        ))
        all_form_types = list(set(
            doc["form_type"] for doc in all_documents 
            if doc["form_type"] and doc["form_type"] != "Unknown"
        ))
        
        logger.info(f"Returning {len(limited_documents)} documents after all filtering")
        
        return SECDocumentLibraryResponse(
            documents=limited_documents,
            total_count=len(filtered_documents),  # Total after filtering, before limit
            total_chunks=sum(doc["chunk_count"] for doc in limited_documents),
            companies=sorted(all_companies),
            form_types=sorted(all_form_types)
        )
        
    except Exception as e:
        logger.error(f"Error getting SEC document library: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get document library: {str(e)}")

@router.get("/test-index")
async def test_search_index(
    sec_service: SECDocumentService = Depends(get_sec_service)
):
    """
    Test endpoint to check search index status
    """
    try:
        logger.info("Testing search index")
          # Try a simple search to see if the index has any data
        try:
            # First try to get all documents without any query
            results = sec_service.azure_manager.search_client.search(
                search_text="*",
                top=10,
                select=["id", "document_id", "content", "company", "form_type"]
            )
            
            result_list = list(results)
            logger.info(f"Direct search found {len(result_list)} results")
            
            return {
                "index_status": "accessible",
                "total_results": len(result_list),
                "sample_results": result_list[:3] if result_list else [],
                "message": f"Found {len(result_list)} documents in index"
            }
            
        except Exception as search_error:
            logger.error(f"Direct search failed: {search_error}")
            return {
                "index_status": "error",
                "error": str(search_error),
                "message": "Search index is not accessible"
            }
        
    except Exception as e:
        logger.error(f"Test index error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to test index: {str(e)}")

async def process_single_document_with_progress(
    filing_request: ProcessDocumentRequest,
    sec_service: SECDocumentService,
    batch_id: str,
    progress_callback=None
) -> ProcessDocumentResponse:
    """Process a single document with progress tracking"""
    start_time = time.time()
    document_id = f"{filing_request.ticker}_{filing_request.accession_number}"
    
    # Initialize progress tracking
    progress = DocumentProcessingProgress(
        document_id=document_id,
        ticker=filing_request.ticker,
        accession_number=filing_request.accession_number,
        stage=ProcessingStage.QUEUED,
        progress_percent=0.0,
        message="Queued for processing",
        started_at=datetime.now(),
        updated_at=datetime.now()
    )
    
    async def update_progress(stage: ProcessingStage, percent: float, message: str):
        progress.stage = stage
        progress.progress_percent = percent
        progress.message = message
        progress.updated_at = datetime.now()
        logger.info(f"Document {document_id}: {stage.value} ({percent:.1f}%) - {message}")
        if progress_callback:
            await progress_callback(progress)
    
    # Immediately notify that processing has started
    if progress_callback:
        await progress_callback(progress)
    
    try:
        # Update progress: Starting download
        await update_progress(ProcessingStage.DOWNLOADING, 10.0, "Downloading document from SEC EDGAR")
        
        # Check if document already exists by searching for it in the index
        try:
            existing_docs = await sec_service.azure_manager.hybrid_search(
                query="*",
                filters=f"accession_number eq '{filing_request.accession_number}'",
                top_k=1
            )
            if existing_docs:
                await update_progress(ProcessingStage.COMPLETED, 100.0, "Document already exists, skipping")
                
                progress.completed_at = datetime.now()
                return ProcessDocumentResponse(
                    document_id=document_id,
                    chunks_created=0,
                    metadata={"status": "skipped", "reason": "Already exists in knowledge base"},
                    filing_info={"ticker": filing_request.ticker, "accession_number": filing_request.accession_number},
                    skipped=True,
                    processing_time_seconds=time.time() - start_time,
                    tokens_used=0
                )
        except Exception as search_error:
            # If search fails, continue with processing (don't skip)
            logger.warning(f"Could not check if document exists, continuing with processing: {search_error}")
        
        # Update progress: Parsing
        await update_progress(ProcessingStage.PARSING, 30.0, "Parsing document content")
        
        # Process the document
        result = await sec_service.retrieve_and_process_document(
            ticker=filing_request.ticker,
            accession_number=filing_request.accession_number,
            document_id=filing_request.document_id,
            progress_callback=lambda stage, percent, msg: update_progress(
                ProcessingStage.CHUNKING if "chunk" in msg.lower() else
                ProcessingStage.EMBEDDING if "embedding" in msg.lower() else
                ProcessingStage.INDEXING if "index" in msg.lower() else
                ProcessingStage.PARSING,
                30.0 + (percent * 0.6),  # Scale to 30-90% range
                msg
            )
        )
        
        # Update progress: Completed
        await update_progress(ProcessingStage.COMPLETED, 100.0, "Document processing completed")
        
        progress.completed_at = datetime.now()
        progress.chunks_created = result.get("chunk_count", 0)
        
        return ProcessDocumentResponse(
            document_id=document_id,
            chunks_created=result.get("chunk_count", 0),
            metadata=result.get("metadata", {}),
            filing_info=result.get("filing_info", {}),
            skipped=False,
            processing_time_seconds=time.time() - start_time,
            tokens_used=result.get("tokens_used", 0)
        )
        
    except Exception as e:
        logger.error(f"Error processing document {document_id}: {e}")
        
        # Categorize the error for better user feedback
        error_message = str(e)
        error_category = "processing_error"
        
        if "Filing not found" in error_message:
            error_category = "filing_not_found"
            error_message = f"SEC filing not found: {filing_request.accession_number}. This filing may not exist for ticker '{filing_request.ticker}' or may be too old to be available in the SEC database."
        elif "Azure" in error_message or "search" in error_message.lower():
            error_category = "azure_service_error"
            error_message = f"Azure service error: {error_message}"
        elif "embedding" in error_message.lower():
            error_category = "embedding_error"
            error_message = f"Embedding generation failed: {error_message}"
        elif "download" in error_message.lower() or "retriev" in error_message.lower():
            error_category = "download_error"
            error_message = f"Document download failed: {error_message}"
        
        # Update progress: Failed
        await update_progress(ProcessingStage.FAILED, 0.0, f"Processing failed: {error_message}")
        progress.error_message = error_message
        progress.completed_at = datetime.now()
        
        return ProcessDocumentResponse(
            document_id=document_id,
            chunks_created=0,
            metadata={
                "status": "error", 
                "message": error_message,
                "error_category": error_category,
                "original_error": str(e)
            },
            filing_info={"ticker": filing_request.ticker, "accession_number": filing_request.accession_number},
            skipped=False,
            processing_time_seconds=time.time() - start_time,
            tokens_used=0
        )

@router.delete("/documents/{document_id}")
async def delete_sec_document(
    document_id: str,
    sec_service: SECDocumentService = Depends(get_sec_service)
):
    """
    Delete a SEC document and all its chunks from the vector store
    """
    try:
        logger.info(f"Deleting SEC document: {document_id}")
        
        # Search for all chunks belonging to this document
        chunks_to_delete = await sec_service.azure_manager.hybrid_search(
            query="*",
            filters=f"document_id eq '{document_id}'",
            top_k=10000  # Large number to get all chunks
        )
        
        if not chunks_to_delete:
            raise HTTPException(status_code=404, detail="Document not found")
        
        logger.info(f"Found {len(chunks_to_delete)} chunks to delete for document {document_id}")
        
        # Delete all chunks from the search index
        chunk_ids_to_delete = [chunk.get('id') for chunk in chunks_to_delete if chunk.get('id')]
        
        if chunk_ids_to_delete:
            # Delete chunks in batches to avoid overwhelming the search service
            batch_size = 100
            deleted_count = 0
            
            for i in range(0, len(chunk_ids_to_delete), batch_size):
                batch = chunk_ids_to_delete[i:i + batch_size]
                try:
                    # Create documents to delete (just need the id field)
                    delete_documents = [{"id": chunk_id} for chunk_id in batch]
                    
                    # Upload the delete batch
                    result = await sec_service.azure_manager.search_client.delete_documents(delete_documents)
                    deleted_count += len(batch)
                    logger.info(f"Deleted batch of {len(batch)} chunks (total: {deleted_count}/{len(chunk_ids_to_delete)})")
                    
                except Exception as batch_error:
                    logger.error(f"Error deleting batch: {batch_error}")
                    # Continue with next batch even if one fails
            
            logger.info(f"Successfully deleted {deleted_count} chunks for document {document_id}")
            
            return {
                "message": f"Successfully deleted document {document_id}",
                "document_id": document_id,
                "chunks_deleted": deleted_count,
                "total_chunks_found": len(chunks_to_delete)
            }
        else:
            logger.warning(f"No chunk IDs found to delete for document {document_id}")
            return {
                "message": f"Document {document_id} had no valid chunks to delete",
                "document_id": document_id,
                "chunks_deleted": 0,
                "total_chunks_found": len(chunks_to_delete)
            }
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting SEC document {document_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete document: {str(e)}")

@router.get("/debug/validate-filing/{ticker}/{accession_number}")
async def validate_filing(
    ticker: str,
    accession_number: str,
    sec_service: SECDocumentService = Depends(get_sec_service)
):
    """
    Debug endpoint to validate if a filing exists and is accessible
    """
    try:
        from edgar import Company
        
        logger.info(f"Validating filing: {ticker} - {accession_number}")
        
        # Get the company
        company = Company(ticker.upper())
        
        # Get recent filings (default limit)
        recent_filings = company.get_filings()
        
        # Check if filing is in recent filings
        found_in_recent = any(f.accession_number == accession_number for f in recent_filings)
        
        # Get extended filings if not found in recent
        found_in_extended = False
        if not found_in_recent:
            try:
                extended_filings = company.get_filings(limit=500)
                found_in_extended = any(f.accession_number == accession_number for f in extended_filings)
            except Exception as e:
                logger.warning(f"Could not get extended filings: {e}")
        
        # Gather information about available filings
        recent_accession_numbers = [f.accession_number for f in recent_filings[:10]]  # First 10
        
        return {
            "ticker": ticker.upper(),
            "accession_number": accession_number,
            "company_name": getattr(company, 'name', 'Unknown'),
            "company_cik": getattr(company, 'cik', 'Unknown'),
            "validation_results": {
                "found_in_recent_filings": found_in_recent,
                "found_in_extended_filings": found_in_extended,
                "is_accessible": found_in_recent or found_in_extended
            },
            "recent_filings_count": len(recent_filings),
            "sample_recent_accession_numbers": recent_accession_numbers,
            "suggestions": {
                "message": "If filing not found, verify the accession number is correct and belongs to this ticker",
                "note": "Some very old filings may not be available through the API"
            }
        }
        
    except Exception as e:
        logger.error(f"Error validating filing: {e}")
        return {
            "ticker": ticker.upper(),
            "accession_number": accession_number,
            "validation_results": {
                "error": str(e),
                "is_accessible": False
            },
            "suggestions": {
                "message": "Error occurred during validation. Check if ticker symbol is valid.",
                "error_details": str(e)
            }
        }

@router.get("/debug/company-info/{ticker}")
async def get_company_debug_info(
    ticker: str,
    sec_service: SECDocumentService = Depends(get_sec_service)
):
    """
    Get detailed company information for debugging
    """
    try:
        from edgar import Company
        
        company = Company(ticker.upper())
        
        # Get recent filings
        filings = company.get_filings(limit=20)
        
        filing_summary = []
        for filing in filings:
            filing_summary.append({
                "accession_number": filing.accession_number,
                "form_type": filing.form,
                "filing_date": filing.filing_date.isoformat() if filing.filing_date else None,
                "period_end_date": filing.period_end_date.isoformat() if hasattr(filing, 'period_end_date') and filing.period_end_date else None,
            })
        
        return {
            "ticker": ticker.upper(),
            "company_name": getattr(company, 'name', 'Unknown'),
            "cik": str(getattr(company, 'cik', 'Unknown')).zfill(10),
            "industry": getattr(company, 'industry', 'Unknown'),
            "sic": getattr(company, 'sic', 'Unknown'),
            "entity_type": getattr(company, 'entity_type', 'Unknown'),
            "recent_filings": filing_summary,
            "total_recent_filings": len(filings)
        }
        
    except Exception as e:
        logger.error(f"Error getting company info: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get company info: {str(e)}")
