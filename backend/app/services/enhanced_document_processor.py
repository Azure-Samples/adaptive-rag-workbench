import hashlib
import asyncio
import time
from pathlib import Path
from typing import Dict, Any, List, Optional, Callable
from ..ingestion.di_extract import extract_pdf_content
from .azure_services import get_azure_service_manager
import logging

logger = logging.getLogger(__name__)

class EnhancedDocumentProcessor:
    """
    Enhanced document processor that combines Azure Document Intelligence extraction
    with intelligent chunking and indexing capabilities.
    """
    
    def __init__(self):
        self.chunk_size = 4000  # Increased to ~4000 chars (~1000 tokens) for better context
        self.chunk_overlap = 200

    async def process_document(self, file_path: str, filename: str, status_callback: Optional[Callable] = None) -> Dict[str, Any]:
        """
        Process a document from start to finish: extract content, create chunks, and index
        
        Args:
            file_path: Path to the document file
            filename: Original filename
            status_callback: Optional callback function for status updates
            
        Returns:
            Dict containing processing results with chunks and metadata
        """
        processing_start_time = time.time()
        
        def update_status(step: str, message: str, progress: int = 0):
            """Helper to update status and log with better error handling"""
            # Truncate long messages for logging
            log_message = message[:100] + "..." if len(message) > 100 else message
            logger.info(f"[{filename}] {step}: {log_message} ({progress}%)")
            
            if status_callback:
                try:
                    status_callback({
                        "step": step,
                        "message": message,
                        "progress": progress,
                        "filename": filename
                    })
                except Exception as callback_error:
                    logger.error(f"[{filename}] Status callback error: {str(callback_error)}")
        
        try:
            file_path_obj = Path(file_path)
            file_size = file_path_obj.stat().st_size
            
            update_status("VALIDATION", f"✅ File validated: {filename} ({file_size:,} bytes)", 5)
            await asyncio.sleep(0.1)  # Allow UI to update
            
            # Determine file type and use appropriate extraction method
            file_extension = file_path_obj.suffix.lower()
            
            update_status("EXTRACTION", f"🔍 Starting {file_extension.upper()} analysis with Document Intelligence", 10)
            await asyncio.sleep(0.1)
            
            # Quick feedback that extraction is proceeding
            update_status("EXTRACTION", "📊 Connecting to Azure Document Intelligence service...", 12)
            await asyncio.sleep(0.2)
            
            try:
                if file_extension == '.pdf':
                    doc_result = await extract_pdf_content(file_path_obj)
                elif file_extension in ['.html', '.htm']:
                    from ..ingestion.di_extract import extract_html_content
                    doc_result = await extract_html_content(file_path_obj)
                else:
                    raise Exception(f"Unsupported file type: {file_extension}")
            except Exception as extraction_error:
                error_msg = f"Content extraction failed: {str(extraction_error)}"
                logger.error(f"[{filename}] {error_msg}")
                update_status("EXTRACTION", error_msg, 0)
                raise Exception(error_msg)
            
            # Check extraction results
            content = doc_result.get("content", "")
            logger.info(f"[{filename}] Content check: length={len(content)}, type={type(content)}")
            logger.info(f"[{filename}] Content preview: {repr(content[:200])}")
            logger.info(f"[{filename}] doc_result keys: {list(doc_result.keys())}")
            
            # Check for actual extraction errors, not just the word "Error" in content
            if not content or len(content.strip()) == 0:
                error_msg = f"No valid content extracted from document"
                logger.error(f"[{filename}] {error_msg}")
                update_status("EXTRACTION", error_msg, 0)
                raise Exception(error_msg)
            
            # Check if content indicates an extraction error (more specific check)
            if content.strip().startswith("Error:") or "extraction failed" in content.lower():
                error_msg = f"Content extraction failed: {content[:200]}"
                logger.error(f"[{filename}] {error_msg}")
                update_status("EXTRACTION", error_msg, 0)
                raise Exception(error_msg)
            
            content_length = len(content)
            update_status("EXTRACTION", f"Content extracted successfully ({content_length:,} characters)", 25)
            await asyncio.sleep(0.1)
            
            # Extract metadata with enhanced logging
            update_status("METADATA", "Extracting document metadata", 30)
            await asyncio.sleep(0.1)
            
            try:
                company = self._extract_company(filename, content)
                document_type = self._extract_document_type(filename, content)
                year = self._extract_year(filename, content)
                
                logger.info(f"[{filename}] Metadata: Company={company}, Type={document_type}, Year={year}")
                update_status("METADATA", f"Identified: {company} - {document_type} ({year})", 35)
                await asyncio.sleep(0.1)
            except Exception as metadata_error:
                logger.warning(f"[{filename}] Metadata extraction had issues: {str(metadata_error)}")
                company, document_type, year = "Unknown", "Document", "2024"
                update_status("METADATA", "Using default metadata due to extraction issues", 35)
            
            # Perform credibility assessment
            update_status("ASSESSMENT", "Performing credibility assessment", 40)
            await asyncio.sleep(0.1)
            
            try:
                credibility_score = self._assess_document_credibility(doc_result, filename)
                logger.info(f"[{filename}] Credibility score: {credibility_score:.2f}")
                update_status("ASSESSMENT", f"Credibility score: {credibility_score:.2f}", 45)
                await asyncio.sleep(0.1)
            except Exception as credibility_error:
                logger.warning(f"[{filename}] Credibility assessment failed: {str(credibility_error)}")
                credibility_score = 0.5
                update_status("ASSESSMENT", "Using default credibility score", 45)
            
            # Create intelligent chunks
            update_status("CHUNKING", "Creating intelligent document chunks", 50)
            await asyncio.sleep(0.1)
            
            try:
                chunks = self._create_intelligent_chunks(doc_result, filename, company, year)
                
                if not chunks:
                    logger.warning(f"[{filename}] No chunks created from document")
                    update_status("CHUNKING", "No chunks created - document may be too short", 60)
                else:
                    update_status("CHUNKING", f"Generated {len(chunks)} chunks", 60)
                    logger.info(f"[{filename}] Chunk statistics: {self._get_chunk_statistics(chunks)}")
                    await asyncio.sleep(0.1)
            except Exception as chunking_error:
                logger.error(f"[{filename}] Chunking failed: {str(chunking_error)}")
                chunks = []
                update_status("CHUNKING", f"Chunking failed: {str(chunking_error)}", 60)
            
            # Generate embeddings using Azure Service Manager
            embedding_success_count = 0
            if chunks:
                update_status("EMBEDDINGS", "Generating vector embeddings", 70)
                await asyncio.sleep(0.1)
                
                try:
                    azure_service = await get_azure_service_manager()
                    
                    # Process embeddings in smaller batches for better progress tracking
                    batch_size = 5
                    for i in range(0, len(chunks), batch_size):
                        batch = chunks[i:i + batch_size]
                        batch_num = i // batch_size + 1
                        total_batches = (len(chunks) + batch_size - 1) // batch_size
                        
                        update_status("EMBEDDINGS", f"Processing batch {batch_num}/{total_batches}", 70 + (batch_num * 10 // total_batches))
                        
                        for chunk in batch:
                            try:
                                content_text = chunk.get('content', '')
                                if content_text:
                                    embedding = await azure_service.get_embedding(content_text)
                                    if embedding:
                                        chunk['content_vector'] = embedding
                                        chunk['embedding_model'] = 'text-embedding-3-small'
                                        chunk['embedding_dimensions'] = len(embedding)
                                        embedding_success_count += 1
                            except Exception as single_embedding_error:
                                logger.warning(f"[{filename}] Failed to generate embedding for chunk: {str(single_embedding_error)}")
                                continue
                        
                        await asyncio.sleep(0.1)  # Allow UI updates between batches
                    
                    logger.info(f"[{filename}] Generated {embedding_success_count}/{len(chunks)} embeddings")
                    update_status("EMBEDDINGS", f"Generated {embedding_success_count} vector embeddings", 80)
                    await asyncio.sleep(0.1)
                    
                except Exception as embedding_error:
                    logger.warning(f"[{filename}] Embedding generation failed: {str(embedding_error)}")
                    update_status("EMBEDDINGS", f"Embedding generation failed: {str(embedding_error)}", 80)
            
            # Index chunks in Azure Search with enhanced error handling
            if chunks:
                update_status("INDEXING", f"Setting up Azure Search index", 83)
                await asyncio.sleep(0.1)
                
                # Ensure the search index exists with the correct schema
                try:
                    from .search_index_setup import setup_vector_search_index
                    await setup_vector_search_index()
                    logger.info(f"[{filename}] Search index setup completed")
                except Exception as index_setup_error:
                    logger.warning(f"[{filename}] Index setup failed: {str(index_setup_error)}")
                
                update_status("INDEXING", f"Indexing {len(chunks)} chunks in Azure Search", 85)
                await asyncio.sleep(0.1)
                
                try:
                    # Add enhanced metadata to chunks before indexing
                    enhanced_chunks = []
                    for i, chunk in enumerate(chunks):
                        enhanced_chunk = chunk.copy()
                        enhanced_chunk.update({
                            "document_type": document_type,
                            "chunk_index": i,
                            "filing_date": f"{year}-12-31",
                            "content_length": len(chunk.get('content', '')),
                            "word_count": len(chunk.get('content', '').split()),
                            "credibility_score": credibility_score,
                            "has_structured_content": bool(doc_result.get('structure_info', {})),
                            "structure_info": str(doc_result.get('structure_info', {})),
                            "chunk_id": chunk.get('id', ''),
                            "embedding_model": chunk.get('embedding_model', ''),
                            "embedding_dimensions": chunk.get('embedding_dimensions', 0)
                        })
                        enhanced_chunks.append(enhanced_chunk)
                    
                    # Upload to Azure Search index using Azure Service Manager
                    azure_service = await get_azure_service_manager()
                    indexing_success = await azure_service.add_documents_to_index(enhanced_chunks)
                    
                    if indexing_success:
                        update_status("INDEXING", "Successfully indexed all chunks", 95)
                        logger.info(f"[{filename}] Indexing completed successfully")
                    else:
                        update_status("INDEXING", "Indexing completed with warnings", 95)
                        logger.warning(f"[{filename}] Indexing completed but with some issues")
                    await asyncio.sleep(0.1)
                    
                except Exception as index_error:
                    logger.error(f"[{filename}] Indexing failed: {str(index_error)}")
                    update_status("INDEXING", f"Indexing failed: {str(index_error)}", 95)
            else:
                logger.warning(f"[{filename}] No chunks created for indexing")
                update_status("INDEXING", "No chunks to index", 95)
            
            processing_time = time.time() - processing_start_time
            
            # Prepare comprehensive response
            result = {
                "chunks": chunks,
                "metadata": {
                    "company": company,
                    "document_type": document_type,
                    "year": year,
                    "filename": filename,
                    "total_chunks": len(chunks),
                    "content_length": content_length,
                    "file_size": file_size,
                    "credibility_score": credibility_score,
                    "processing_time_seconds": round(processing_time, 2),
                    "embedding_success_count": embedding_success_count,
                    "extraction_metadata": doc_result.get("document_metadata", {}),
                    "structure_info": doc_result.get("structure_info", {})
                },
                "status": "success"
            }
            
            update_status("COMPLETED", f"Processing completed in {processing_time:.2f}s", 100)
            logger.info(f"[{filename}] Successfully processed: {len(chunks)} chunks, credibility: {credibility_score:.2f}")
            
            return result
            
        except Exception as e:
            error_msg = str(e)
            processing_time = time.time() - processing_start_time
            logger.error(f"[{filename}] Error processing document after {processing_time:.2f}s: {error_msg}")
            update_status("ERROR", f"Processing failed: {error_msg}", 0)
            raise Exception(f"Document processing failed: {error_msg}")

    def _create_chunks(self, doc_result: Dict[str, Any], filename: str, company: str, year: str) -> List[Dict[str, Any]]:
        """
        Create semantic chunks from document content with proper size limits
        """
        content = doc_result.get("content", "")
        if not content:
            return []
        
        chunks = []
        
        # Split content into sentences first for better semantic boundaries
        sentences = content.replace('\n', ' ').split('. ')
        current_chunk = ""
        chunk_index = 0
        
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
                
            # Add period back if it was removed (except for last sentence)
            if not sentence.endswith('.') and not sentence.endswith('?') and not sentence.endswith('!'):
                sentence += '.'
            
            # Check if adding this sentence would exceed chunk size
            potential_chunk = current_chunk + (" " + sentence if current_chunk else sentence)
            
            if len(potential_chunk) > self.chunk_size and current_chunk:
                # Finalize current chunk
                chunk = self._create_chunk_dict(
                    current_chunk, filename, company, year, chunk_index
                )
                chunks.append(chunk)
                chunk_index += 1
                
                # Start new chunk with overlap - take last few words from previous chunk
                overlap_words = current_chunk.split()[-50:]  # Take last 50 words for overlap
                current_chunk = " ".join(overlap_words) + " " + sentence
            else:
                current_chunk = potential_chunk
        
        # Add final chunk if there's remaining content
        if current_chunk.strip():
            chunk = self._create_chunk_dict(
                current_chunk, filename, company, year, chunk_index
            )
            chunks.append(chunk)
        
        # If we still have chunks that are too large, split them further
        final_chunks = []
        for chunk in chunks:
            if len(chunk['content']) > self.chunk_size:
                # Split large chunks by word count
                words = chunk['content'].split()
                word_chunk_size = self.chunk_size // 6  # Approximate words per chunk (avg 6 chars per word)
                
                for i in range(0, len(words), word_chunk_size):
                    chunk_words = words[i:i + word_chunk_size]
                    if chunk_words:
                        sub_chunk = self._create_chunk_dict(
                            " ".join(chunk_words), filename, company, year, 
                            len(final_chunks)
                        )
                        final_chunks.append(sub_chunk)
            else:
                # Update chunk index for final list
                chunk['chunk_index'] = len(final_chunks)
                final_chunks.append(chunk)
        
        return final_chunks

    def _create_chunk_dict(self, content: str, filename: str, company: str, year: str, index: int) -> Dict[str, Any]:
        """
        Create a standardized chunk dictionary
        """
        # Create unique chunk ID
        chunk_id = hashlib.md5(f"{filename}_{index}_{content[:100]}".encode()).hexdigest()
        
        return {
            "id": chunk_id,
            "content": content.strip(),
            "source": filename,
            "company": company,
            "year": year,
            "chunk_index": index,
            "filing_date": f"{year}-12-31",  # Default filing date
            "document_type": self._extract_document_type(filename),
            "chunk_id": chunk_id
        }

    def _extract_company(self, filename: str, content: str = "") -> str:
        """Extract company name from filename or content"""
        # Try to extract from filename first
        filename_lower = filename.lower()
        companies = {
            'meta': 'Meta',
            'facebook': 'Meta', 
            'fb': 'Meta',
            'apple': 'Apple',
            'aapl': 'Apple',
            'google': 'Google',
            'alphabet': 'Google',
            'googl': 'Google',
            'goog': 'Google',
            'microsoft': 'Microsoft',
            'msft': 'Microsoft',
            'amazon': 'Amazon',
            'amzn': 'Amazon',
            'tesla': 'Tesla',
            'tsla': 'Tesla',
            'netflix': 'Netflix',
            'nflx': 'Netflix',
            'nvidia': 'NVIDIA',
            'nvda': 'NVIDIA'
        }
        
        for key, company in companies.items():
            if key in filename_lower:
                return company
        
        # Try to extract from content if available
        if content:
            content_lower = content.lower()
            for key, company in companies.items():
                if key in content_lower:
                    return company
        
        return "Unknown"

    def _extract_document_type(self, filename: str, content: str = "") -> str:
        """Extract document type from filename or content"""
        filename_lower = filename.lower()
        content_lower = content.lower() if content else ""
        
        if '10-k' in filename_lower or '10-k' in content_lower:
            return '10-K'
        elif '10-q' in filename_lower or '10-q' in content_lower:
            return '10-Q'
        elif 'earnings' in filename_lower or 'earnings' in content_lower:
            return 'Earnings Report'
        elif 'annual' in filename_lower or 'annual' in content_lower:
            return 'Annual Report'
        else:
            return 'Financial Document'

    def _extract_year(self, filename: str, content: str = "") -> str:
        """Extract year from filename or content"""
        import re
        
        # Try to extract year from filename
        year_match = re.search(r'20\d{2}', filename)
        if year_match:
            return str(year_match.group())
        
        # Try to extract from content
        if content:
            year_matches = re.findall(r'20\d{2}', content[:1000])  # Check first 1000 chars
            if year_matches:
                # Return the most recent year found
                return str(max(int(year) for year in year_matches))
        
        return "2024"  # Default to current year

    def _assess_document_credibility(self, doc_result: Dict[str, Any], filename: str) -> float:
        """
        Assess document credibility based on structure, content, and metadata
        Returns a score between 0.0 and 1.0
        """
        try:
            score = 0.0
            max_score = 10.0
            
            # Check content length (longer documents typically more credible for financial docs)
            content = doc_result.get("content", "")
            if len(content) > 50000:  # Substantial content
                score += 2.0
            elif len(content) > 10000:
                score += 1.0
            
            # Check for structured content (tables, paragraphs)
            structure_info = doc_result.get("structure_info", {})
            credibility_indicators = structure_info.get("credibility_indicators", {})
            
            if credibility_indicators.get("has_tables", False):
                score += 2.0  # Financial documents typically have tables
            
            if credibility_indicators.get("has_structured_content", False):
                score += 1.5
            
            if credibility_indicators.get("professional_formatting", False):
                score += 1.5
            
            # Check for financial document keywords
            content_upper = content.upper()
            financial_keywords = [
                "SECURITIES AND EXCHANGE COMMISSION", "SEC", "10-K", "10-Q", 
                "FINANCIAL STATEMENTS", "CONSOLIDATED", "REVENUE", "ASSETS",
                "LIABILITIES", "CASH FLOW", "BALANCE SHEET"
            ]
            
            keyword_count = sum(1 for keyword in financial_keywords if keyword in content_upper)
            score += min(keyword_count * 0.3, 2.0)  # Cap at 2.0
            
            # Check document metadata
            doc_metadata = doc_result.get("document_metadata", {})
            if doc_metadata.get("page_count", 0) > 10:
                score += 1.0  # Substantial document
            
            # Normalize score to 0-1 range
            normalized_score = min(score / max_score, 1.0)
            
            logger.debug(f"[{filename}] Credibility assessment: Raw score={score:.1f}, Normalized={normalized_score:.2f}")
            return normalized_score
            
        except Exception as e:
            logger.error(f"Error assessing credibility for {filename}: {str(e)}")
            return 0.5  # Default medium credibility

    def _create_intelligent_chunks(self, doc_result: Dict[str, Any], filename: str, company: str, year: str) -> List[Dict[str, Any]]:
        """
        Create intelligent chunks using document structure awareness
        """
        try:
            # Use enhanced chunking if paragraphs are available
            paragraphs = doc_result.get("paragraphs", [])
            if paragraphs:
                return self._create_structure_aware_chunks(doc_result, filename, company, year)
            else:
                # Fallback to traditional chunking
                return self._create_chunks(doc_result, filename, company, year)
                
        except Exception as e:
            logger.error(f"Error creating intelligent chunks for {filename}: {str(e)}")
            # Fallback to basic chunking
            return self._create_chunks(doc_result, filename, company, year)

    def _create_structure_aware_chunks(self, doc_result: Dict[str, Any], filename: str, company: str, year: str) -> List[Dict[str, Any]]:
        """
        Create chunks that respect document structure (paragraphs, sections) with proper size limits
        """
        paragraphs = doc_result.get("paragraphs", [])
        chunks = []
        current_chunk_content = ""
        current_chunk_paragraphs = []
        chunk_index = 0
        
        for paragraph in paragraphs:
            para_content = paragraph.get("content", "").strip()
            para_role = paragraph.get("role", "paragraph")
            
            if not para_content:
                continue
            
            # Check if this paragraph would make the chunk too large
            potential_content = current_chunk_content + (" " + para_content if current_chunk_content else para_content)
            
            if len(potential_content) > self.chunk_size and current_chunk_content:
                # Finalize current chunk
                chunk = self._create_enhanced_chunk_dict(
                    current_chunk_content, filename, company, year, chunk_index,
                    structure_info={
                        "paragraph_count": len(current_chunk_paragraphs),
                        "roles": list(set(p.get("role", "paragraph") for p in current_chunk_paragraphs))
                    }
                )
                chunks.append(chunk)
                chunk_index += 1
                
                # Start new chunk with potential overlap
                if para_role in ["title", "sectionHeading"]:
                    # Start fresh for headers
                    current_chunk_content = para_content
                    current_chunk_paragraphs = [paragraph]
                else:
                    # Include overlap from previous chunk
                    overlap_paras = current_chunk_paragraphs[-1:] if current_chunk_paragraphs else []
                    overlap_content = " ".join(p.get("content", "") for p in overlap_paras)
                    if overlap_content:
                        current_chunk_content = overlap_content + " " + para_content
                    else:
                        current_chunk_content = para_content
                    current_chunk_paragraphs = overlap_paras + [paragraph]
            else:
                # Add to current chunk
                current_chunk_content = potential_content
                current_chunk_paragraphs.append(paragraph)
        
        # Add final chunk if there's remaining content
        if current_chunk_content.strip():
            chunk = self._create_enhanced_chunk_dict(
                current_chunk_content, filename, company, year, chunk_index,
                structure_info={
                    "paragraph_count": len(current_chunk_paragraphs),
                    "roles": list(set(p.get("role", "paragraph") for p in current_chunk_paragraphs))
                }
            )
            chunks.append(chunk)
        
        # Post-process to ensure no chunks are too large
        final_chunks = []
        for chunk in chunks:
            if len(chunk['content']) > self.chunk_size:
                # Split large chunks by sentences
                sentences = chunk['content'].split('. ')
                sub_chunk_content = ""
                sub_chunk_index = 0
                
                for sentence in sentences:
                    sentence = sentence.strip()
                    if not sentence:
                        continue
                        
                    if not sentence.endswith('.') and not sentence.endswith('?') and not sentence.endswith('!'):
                        sentence += '.'
                    
                    potential_sub_chunk = sub_chunk_content + (" " + sentence if sub_chunk_content else sentence)
                    
                    if len(potential_sub_chunk) > self.chunk_size and sub_chunk_content:
                        # Create sub-chunk
                        sub_chunk = self._create_enhanced_chunk_dict(
                            sub_chunk_content, filename, company, year, 
                            len(final_chunks),
                            structure_info=chunk.get('structure_info', {})
                        )
                        final_chunks.append(sub_chunk)
                        sub_chunk_content = sentence
                    else:
                        sub_chunk_content = potential_sub_chunk
                
                # Add final sub-chunk
                if sub_chunk_content.strip():
                    sub_chunk = self._create_enhanced_chunk_dict(
                        sub_chunk_content, filename, company, year, 
                        len(final_chunks),
                        structure_info=chunk.get('structure_info', {})
                    )
                    final_chunks.append(sub_chunk)
            else:
                chunk['chunk_index'] = len(final_chunks)
                final_chunks.append(chunk)
        
        logger.info(f"[{filename}] Structure-aware chunking: {len(paragraphs)} paragraphs → {len(final_chunks)} chunks")
        return final_chunks

    def _create_enhanced_chunk_dict(self, content: str, filename: str, company: str, year: str, index: int, structure_info: Dict = None) -> Dict[str, Any]:
        """
        Create an enhanced chunk dictionary with additional metadata
        """
        # Create unique chunk ID
        chunk_id = hashlib.md5(f"{filename}_{index}_{content[:100]}".encode()).hexdigest()
        
        chunk_data = {
            "id": chunk_id,
            "content": content.strip(),
            "source": filename,
            "company": company,
            "year": year,
            "chunk_index": index,
            "filing_date": f"{year}-12-31",  # Default filing date
            "document_type": self._extract_document_type(filename),
            "chunk_id": chunk_id,
            "content_length": len(content),
            "word_count": len(content.split()),
        }
        
        # Add structure information if available
        if structure_info:
            chunk_data.update({
                "structure_info": structure_info,
                "has_structured_content": True
            })
        
        return chunk_data

    def _get_chunk_statistics(self, chunks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Generate statistics about the created chunks
        """
        if not chunks:
            return {"total_chunks": 0}
        
        content_lengths = [len(chunk.get("content", "")) for chunk in chunks]
        word_counts = [len(chunk.get("content", "").split()) for chunk in chunks]
        
        return {
            "total_chunks": len(chunks),
            "avg_content_length": sum(content_lengths) / len(content_lengths),
            "min_content_length": min(content_lengths),
            "max_content_length": max(content_lengths),
            "avg_word_count": sum(word_counts) / len(word_counts),
            "total_words": sum(word_counts),
            "has_structure_info": any(chunk.get("structure_info") for chunk in chunks)
        }    