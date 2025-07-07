import asyncio
import logging
import time
import json
from pathlib import Path
from typing import Dict, Any, Optional, Callable
from ..ingestion.di_extract import extract_content_from_pdf, extract_content_from_html
from ..services.embedding_service import EmbeddingService
from ..ingestion.indexer_job import upsert_chunks
from ..ingestion.chunk import chunk_content

class ModularDocumentProcessor:
    """
    Modular document processor that provides granular status updates
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.embedding_service = EmbeddingService()
        
    async def process_document(self, file_path: str, filename: str, status_callback: Optional[Callable] = None) -> Dict[str, Any]:
        """
        Process document with granular status updates
        """
        start_time = time.time()
        
        # Initialize result structure
        result = {
            "chunks": [],
            "metadata": {
                "filename": filename,
                "file_path": file_path,
                "processing_steps": [],
                "errors": []
            }
        }
        
        try:
            # Step 1: File Validation
            await self._update_status(status_callback, "VALIDATION", "Starting file validation...", 0)
            validation_result = await self._validate_file(file_path, filename)
            result["metadata"]["file_size"] = validation_result.get("file_size", 0)
            await self._update_status(status_callback, "VALIDATION", "File validation completed", 10)
            await asyncio.sleep(0.5)  # Allow UI to update
            
            # Step 2: Content Extraction
            await self._update_status(status_callback, "EXTRACTION", "Extracting content from document...", 15)
            extraction_result = await self._extract_content(file_path, filename)
            result["metadata"]["extraction_stats"] = extraction_result.get("stats", {})
            await self._update_status(status_callback, "EXTRACTION", f"Extracted {len(extraction_result.get('text', ''))} characters", 25)
            await asyncio.sleep(0.5)
            
            # Step 3: Metadata Analysis
            await self._update_status(status_callback, "METADATA", "Analyzing document metadata...", 30)
            metadata_result = await self._analyze_metadata(extraction_result, filename)
            result["metadata"].update(metadata_result)
            await self._update_status(status_callback, "METADATA", f"Identified company: {metadata_result.get('company', 'Unknown')}", 40)
            await asyncio.sleep(0.5)
            
            # Step 4: Credibility Assessment
            await self._update_status(status_callback, "ASSESSMENT", "Evaluating document credibility...", 45)
            credibility_result = await self._assess_credibility(extraction_result, metadata_result)
            result["metadata"]["credibility_score"] = credibility_result.get("score", 0.5)
            await self._update_status(status_callback, "ASSESSMENT", f"Credibility score: {credibility_result.get('score', 0.5):.2f}", 55)
            await asyncio.sleep(0.5)
            
            # Step 5: Intelligent Chunking
            await self._update_status(status_callback, "CHUNKING", "Creating intelligent content chunks...", 60)
            chunking_result = await self._create_chunks(extraction_result, metadata_result)
            result["chunks"] = chunking_result.get("chunks", [])
            await self._update_status(status_callback, "CHUNKING", f"Created {len(result['chunks'])} chunks", 70)
            await asyncio.sleep(0.5)
            
            # Step 6: Embedding Generation (if we have chunks)
            if result["chunks"]:
                await self._update_status(status_callback, "EMBEDDINGS", "Generating vector embeddings...", 75)
                embedding_result = await self._generate_embeddings(result["chunks"])
                result["metadata"]["embedding_stats"] = embedding_result.get("stats", {})
                await self._update_status(status_callback, "EMBEDDINGS", f"Generated embeddings for {embedding_result.get('processed_count', 0)} chunks", 85)
                await asyncio.sleep(0.5)
                
                # Step 7: Search Indexing
                await self._update_status(status_callback, "INDEXING", "Indexing content in Azure Search...", 90)
                indexing_result = await self._index_content(result["chunks"])
                result["metadata"]["indexing_stats"] = indexing_result.get("stats", {})
                await self._update_status(status_callback, "INDEXING", f"Indexed {indexing_result.get('indexed_count', 0)} chunks", 100)
            else:
                await self._update_status(status_callback, "INDEXING", "No chunks to index", 100)
            
            # Finalize metadata
            result["metadata"]["processing_time_seconds"] = time.time() - start_time
            result["metadata"]["chunks_created"] = len(result["chunks"])
            result["metadata"]["status"] = "completed"
            
            self.logger.info(f"Successfully processed {filename} in {result['metadata']['processing_time_seconds']:.2f}s")
            return result
            
        except Exception as e:
            error_msg = f"Error processing {filename}: {str(e)}"
            self.logger.error(error_msg)
            result["metadata"]["errors"].append(error_msg)
            result["metadata"]["status"] = "error"
            result["metadata"]["processing_time_seconds"] = time.time() - start_time
            
            # Send error status
            if status_callback:
                try:
                    status_callback({
                        "step": "ERROR",
                        "message": error_msg,
                        "progress": 0
                    })
                except Exception as callback_error:
                    self.logger.error(f"Error in status callback: {callback_error}")
            
            raise
    
    async def _update_status(self, callback: Optional[Callable], step: str, message: str, progress: int):
        """Update processing status"""
        self.logger.info(f"[{step}] {message} ({progress}%)")
        
        if callback:
            try:
                callback({
                    "step": step,
                    "message": message,
                    "progress": progress
                })
            except Exception as e:
                self.logger.error(f"Error in status callback: {e}")
    
    async def _validate_file(self, file_path: str, filename: str) -> Dict[str, Any]:
        """Validate file and get basic info"""
        try:
            file_obj = Path(file_path)
            if not file_obj.exists():
                raise FileNotFoundError(f"File not found: {file_path}")
            
            file_size = file_obj.stat().st_size
            file_extension = file_obj.suffix.lower()
            
            # Basic validation
            if file_size == 0:
                raise ValueError("File is empty")
            
            if file_extension not in ['.pdf', '.html', '.htm']:
                raise ValueError(f"Unsupported file type: {file_extension}")
            
            return {
                "file_size": file_size,
                "file_extension": file_extension,
                "valid": True
            }
        except Exception as e:
            self.logger.error(f"File validation failed: {e}")
            raise
    
    async def _extract_content(self, file_path: str, filename: str) -> Dict[str, Any]:
        """Extract content from document"""
        try:
            file_extension = Path(file_path).suffix.lower()
            
            if file_extension == '.pdf':
                content_data = await extract_content_from_pdf(file_path)
            elif file_extension in ['.html', '.htm']:
                content_data = await extract_content_from_html(file_path)
            else:
                raise ValueError(f"Unsupported file type: {file_extension}")
            
            if not content_data or not content_data.get('text'):
                raise ValueError("No content extracted from document")
            
            return {
                "text": content_data.get('text', ''),
                "structure": content_data.get('structure', {}),
                "pages": content_data.get('pages', []),
                "tables": content_data.get('tables', []),
                "stats": {
                    "text_length": len(content_data.get('text', '')),
                    "page_count": len(content_data.get('pages', [])),
                    "table_count": len(content_data.get('tables', []))
                }
            }
        except Exception as e:
            self.logger.error(f"Content extraction failed: {e}")
            raise
    
    async def _analyze_metadata(self, extraction_result: Dict[str, Any], filename: str) -> Dict[str, Any]:
        """Analyze document metadata"""
        try:
            text = extraction_result.get('text', '')
            
            # Extract company information
            company = self._extract_company_name(text, filename)
            
            # Extract document type
            doc_type = self._extract_document_type(text, filename)
            
            # Extract year and filing date
            year, filing_date = self._extract_dates(text, filename)
            
            return {
                "company": company,
                "document_type": doc_type,
                "year": year,
                "filing_date": filing_date,
                "content_length": len(text),
                "word_count": len(text.split()) if text else 0
            }
        except Exception as e:
            self.logger.error(f"Metadata analysis failed: {e}")
            # Return defaults on error
            return {
                "company": "Unknown",
                "document_type": "Document",
                "year": "2024",
                "filing_date": "2024-12-31",
                "content_length": 0,
                "word_count": 0
            }
    
    async def _assess_credibility(self, extraction_result: Dict[str, Any], metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Assess document credibility"""
        try:
            text = extraction_result.get('text', '')
            structure = extraction_result.get('structure', {})
            
            score = 0.5  # Base score
            factors = []
            
            # Content length factor
            content_length = len(text)
            if content_length > 50000:
                score += 0.2
                factors.append("substantial_content")
            elif content_length > 10000:
                score += 0.1
                factors.append("adequate_content")
            
            # Structure factor
            if structure.get('tables') or structure.get('paragraphs'):
                score += 0.1
                factors.append("structured_content")
            
            # Financial keywords factor
            financial_keywords = ['revenue', 'earnings', 'financial', 'sec', 'filing', '10-k', '10-q']
            if any(keyword in text.lower() for keyword in financial_keywords):
                score += 0.2
                factors.append("financial_content")
            
            # Ensure score is between 0 and 1
            score = max(0.0, min(1.0, score))
            
            return {
                "score": score,
                "factors": factors
            }
        except Exception as e:
            self.logger.error(f"Credibility assessment failed: {e}")
            return {"score": 0.5, "factors": []}
    
    async def _create_chunks(self, extraction_result: Dict[str, Any], metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Create intelligent content chunks"""
        try:
            text = extraction_result.get('text', '')
            if not text:
                return {"chunks": []}
            
            # Use existing chunking logic
            chunks = chunk_content(
                content=text,
                source=metadata.get('filename', 'unknown'),
                company=metadata.get('company', 'Unknown'),
                year=metadata.get('year', "2024")
            )
            
            # Enhance chunks with additional metadata
            enhanced_chunks = []
            for i, chunk in enumerate(chunks):
                enhanced_chunk = chunk.copy()
                enhanced_chunk.update({
                    "document_type": metadata.get('document_type', 'Document'),
                    "chunk_index": i,
                    "filing_date": metadata.get('filing_date', f"{metadata.get('year', '2024')}-12-31"),
                    "content_length": len(chunk.get('content', '')),
                    "word_count": len(chunk.get('content', '').split()),
                    "credibility_score": metadata.get('credibility_score', 0.5),
                    "has_structured_content": bool(extraction_result.get('structure', {})),
                    "structure_info": json.dumps(extraction_result.get('structure', {}))
                })
                enhanced_chunks.append(enhanced_chunk)
            
            return {
                "chunks": enhanced_chunks,
                "stats": {
                    "chunk_count": len(enhanced_chunks),
                    "avg_chunk_size": sum(len(c.get('content', '')) for c in enhanced_chunks) / len(enhanced_chunks) if enhanced_chunks else 0
                }
            }
        except Exception as e:
            self.logger.error(f"Chunking failed: {e}")
            return {"chunks": [], "stats": {}}
    
    async def _generate_embeddings(self, chunks: list) -> Dict[str, Any]:
        """Generate embeddings for chunks"""
        try:
            processed_count = 0
            for chunk in chunks:
                try:
                    content = chunk.get('content', '')
                    if content:
                        embedding = await self.embedding_service.generate_embedding(content)
                        if embedding:
                            chunk['content_vector'] = embedding
                            chunk['embedding_model'] = 'text-embedding-3-small'
                            chunk['embedding_dimensions'] = len(embedding)
                            processed_count += 1
                except Exception as e:
                    self.logger.warning(f"Failed to generate embedding for chunk: {e}")
                    continue
            
            return {
                "processed_count": processed_count,
                "stats": {
                    "embeddings_generated": processed_count,
                    "embedding_model": "text-embedding-3-small"
                }
            }
        except Exception as e:
            self.logger.error(f"Embedding generation failed: {e}")
            return {"processed_count": 0, "stats": {}}
    
    async def _index_content(self, chunks: list) -> Dict[str, Any]:
        """Index content in Azure Search"""
        try:
            if not chunks:
                return {"indexed_count": 0, "stats": {}}
            
            await upsert_chunks(chunks)
            
            return {
                "indexed_count": len(chunks),
                "stats": {
                    "total_indexed": len(chunks),
                    "index_name": "adaptive-rag-index"
                }
            }
        except Exception as e:
            self.logger.error(f"Indexing failed: {e}")
            return {"indexed_count": 0, "stats": {}}
    
    def _extract_company_name(self, text: str, filename: str) -> str:
        """Extract company name from text or filename"""
        # Try to extract from filename first
        filename_lower = filename.lower()
        companies = {
            'meta': 'Meta',
            'facebook': 'Meta',
            'apple': 'Apple',
            'google': 'Google',
            'alphabet': 'Google',
            'microsoft': 'Microsoft',
            'msft': 'Microsoft',
            'amazon': 'Amazon',
            'amzn': 'Amazon',
            'tesla': 'Tesla',
            'tsla': 'Tesla'
        }
        
        for key, company in companies.items():
            if key in filename_lower:
                return company
        
        # Try to extract from text
        text_lower = text.lower()
        for key, company in companies.items():
            if key in text_lower:
                return company
        
        return "Unknown"
    
    def _extract_document_type(self, text: str, filename: str) -> str:
        """Extract document type"""
        filename_lower = filename.lower()
        text_lower = text.lower()
        
        if '10-k' in filename_lower or '10-k' in text_lower:
            return '10-K'
        elif '10-q' in filename_lower or '10-q' in text_lower:
            return '10-Q'
        elif 'earnings' in filename_lower or 'earnings' in text_lower:
            return 'Earnings Report'
        else:
            return 'Financial Document'
    
    def _extract_dates(self, text: str, filename: str) -> tuple:
        """Extract year and filing date"""
        import re
        
        # Try to extract year from filename
        year_match = re.search(r'20\d{2}', filename)
        if year_match:
            year = str(year_match.group())
        else:
            year = "2024"
        
        # Generate filing date
        filing_date = f"{year}-12-31"
        
        return year, filing_date      