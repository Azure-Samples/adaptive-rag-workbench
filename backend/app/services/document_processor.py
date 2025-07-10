import asyncio
import logging
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
import hashlib
import re
from dataclasses import dataclass
import json

from app.services.azure_services import AzureServiceManager
from app.core.config import settings

logger = logging.getLogger(__name__)

@dataclass
class DocumentChunk:
    chunk_id: str
    content: str
    metadata: Dict[str, Any]
    embedding: Optional[List[float]] = None
    citation_info: Optional[Dict[str, Any]] = None

@dataclass
class FinancialTable:
    table_id: str
    title: str
    content: str
    rows: List[List[str]]
    headers: List[str]
    page_number: int
    bounding_box: Optional[Dict] = None

@dataclass
class FinancialSection:
    section_id: str
    title: str
    content: str
    subsections: List['FinancialSection']
    tables: List[FinancialTable]
    page_range: Tuple[int, int]
    section_type: str  # 'business', 'risk_factors', 'financial_statements', etc.

class DocumentProcessor:
    """
    Enhanced document processing service for financial documents
    Handles extraction, chunking, and preparation for knowledge base
    Specialized for 10-K/10-Q and other SEC filings
    """
    
    def __init__(self, azure_manager: AzureServiceManager):
        self.azure_manager = azure_manager
        self.financial_section_patterns = self._initialize_section_patterns()
        self.financial_metrics_patterns = self._initialize_metrics_patterns()
        
    async def process_document(self, content: bytes, content_type: str, 
                             source: str, metadata: Dict = None) -> Dict:
        """
        Enhanced document processing pipeline for financial documents
        
        Args:
            content: Raw document bytes
            content_type: MIME type of the document
            source: Source identifier
            metadata: Additional metadata
            
        Returns:
            Dict containing processed document information with enhanced structure
        """
        try:
            logger.info(f"=== DOCUMENT PROCESSOR START ===")
            logger.info(f"Source: {source}")
            logger.info(f"Content type: {content_type}")
            logger.info(f"Content size: {len(content)} bytes")
            logger.info(f"Metadata: {metadata}")
            
            observability.track_document_processing_start(source, content_type)
            
            logger.info(f"Step 1: Calling Azure Document Intelligence...")
            extracted_content = await self.azure_manager.analyze_document(content, content_type)
            logger.info(f"Step 1 COMPLETE: Document analysis finished")
            logger.info(f"Extracted content length: {len(extracted_content.get('content', ''))}")
            logger.info(f"Tables found: {len(extracted_content.get('tables', []))}")
            
            logger.info(f"Step 2: Generating document ID...")
            document_id = self._generate_document_id(source, extracted_content["content"])
            logger.info(f"Step 2 COMPLETE: Document ID generated: {document_id}")
            
            logger.info(f"Step 3: Extracting financial info...")
            financial_info = await self._extract_comprehensive_financial_info(
                extracted_content, source
            )
            logger.info(f"Step 3 COMPLETE: Financial info extracted: {list(financial_info.keys())}")
            
            logger.info(f"Step 4: Parsing document structure...")
            document_structure = await self._parse_financial_document_structure(
                extracted_content, financial_info
            )
            logger.info(f"Step 4 COMPLETE: Document structure parsed")
            
            logger.info(f"Step 5: Creating markdown chunks...")
            try:
                chunks = await self._create_markdown_chunks(
                    document_structure, 
                    document_id,
                    {**(metadata or {}), **financial_info}
                )
                logger.info(f"Step 5 COMPLETE: Created {len(chunks)} chunks using markdown chunking")
            except Exception as e:
                logger.warning(f"Markdown chunking failed: {e}, falling back to basic chunking")
                # Fallback to basic text chunking
                chunks = await self._create_basic_chunks(
                    extracted_content["content"],
                    document_id,
                    {**(metadata or {}), **financial_info}
                )
                logger.info(f"Step 5 COMPLETE (FALLBACK): Created {len(chunks)} chunks using basic chunking")
            
            logger.info(f"Step 6: Generating embeddings for chunks...")
            # Extract embedding model from metadata
            embedding_model = metadata.get("embedding_model") if metadata else None
            logger.info(f"Using embedding model: {embedding_model or 'default from settings'}")
            
            for i, chunk in enumerate(chunks):
                if i % 5 == 0:  # Log every 5th chunk to avoid spam
                    logger.info(f"Generating embedding for chunk {i+1}/{len(chunks)}")
                chunk.embedding = await self.azure_manager.get_embedding(chunk.content, model=embedding_model)
            logger.info(f"Step 6 COMPLETE: All embeddings generated")
            
            logger.info(f"Step 6 COMPLETE: All embeddings generated")
            
            # logger.info(f"Step 6.5: Uploading document to Azure Storage...")
            # # Upload original document to Azure Storage
            # try:
            #     storage_url = await self.azure_manager.upload_document_to_storage(
            #         content, source, document_id
            #     )
            #     logger.info(f"Step 6.5 COMPLETE: Document uploaded to storage: {storage_url}")
            #     # Add storage URL to metadata
            #     financial_info["storage_url"] = storage_url
            # except Exception as e:
            #     logger.warning(f"Failed to upload document to storage: {e}")
            #     financial_info["storage_url"] = None
            
            logger.info(f"Step 7: Preparing search documents...")
            # Convert chunks to search index format and add to knowledge base
            search_documents = []
            for chunk in chunks:
                search_doc = {
                    "id": f"{document_id}_{chunk.chunk_id}",
                    "content": chunk.content,
                    "title": chunk.metadata.get("title", source),
                    "document_id": document_id,
                    "source": source,
                    "chunk_id": chunk.chunk_id,
                    "document_type": chunk.metadata.get("document_type", "financial"),
                    "company": chunk.metadata.get("company_name", ""),
                    "filing_date": chunk.metadata.get("filing_date", ""),
                    "section_type": chunk.metadata.get("section_type", "general"),
                    "page_number": chunk.metadata.get("page_number", 1),
                    "content_vector": chunk.embedding,
                    "credibility_score": chunk.metadata.get("credibility_score", 0.8),
                    "processed_at": datetime.utcnow().isoformat(),
                    "citation_info": json.dumps(chunk.citation_info or {})
                }
                search_documents.append(search_doc)
            logger.info(f"Step 7 COMPLETE: Prepared {len(search_documents)} search documents")
            
            logger.info(f"Step 8: Adding documents to Azure Search index...")
            # Add documents to Azure Search index
            if search_documents:
                logger.info(f"Attempting to add {len(search_documents)} chunks for document {document_id} to search index")
                success = await self.azure_manager.add_documents_to_index(search_documents)
                if not success:
                    logger.error(f"FAILED to add chunks for document {document_id} to search index")
                else:
                    logger.info(f"SUCCESS: Added {len(search_documents)} chunks for document {document_id} to search index")
            else:
                logger.warning(f"No search documents generated for document {document_id}")
            logger.info(f"Step 8 COMPLETE: Search index update finished")
            
            logger.info(f"Step 9: Extracting key financial metrics...")
            key_metrics = await self._extract_key_financial_metrics(
                extracted_content["content"], financial_info
            )
            logger.info(f"Step 9 COMPLETE: Extracted {len(key_metrics)} key metrics")
            
            logger.info(f"Step 9 COMPLETE: Extracted {len(key_metrics)} key metrics")
            
            logger.info(f"Step 10: Building final processed document...")
            processed_doc = {
                "document_id": document_id,
                "source": source,
                "content_type": content_type,
                "extracted_content": extracted_content,
                "financial_info": financial_info,
                "document_structure": self._structure_to_dict(document_structure),
                "key_metrics": key_metrics,
                "chunks": [self._chunk_to_dict(chunk) for chunk in chunks],
                "processed_at": datetime.utcnow().isoformat(),
                "metadata": {**(metadata or {}), **financial_info},
                "processing_stats": {
                    "total_chunks": len(chunks),
                    "sections_found": len(document_structure.get("sections", [])),
                    "tables_found": len(document_structure.get("tables", [])),
                    "metrics_extracted": len(key_metrics)
                }
            }
            
            observability.track_document_processing_complete(
                document_id, len(chunks), len(key_metrics)
            )
            
            logger.info(f"=== DOCUMENT PROCESSING COMPLETE ===")
            logger.info(f"Document ID: {document_id}")
            logger.info(f"Total chunks: {len(chunks)}")
            logger.info(f"Sections found: {len(document_structure.get('sections', []))}")
            logger.info(f"Tables found: {len(document_structure.get('tables', []))}")
            logger.info(f"Metrics extracted: {len(key_metrics)}")
            logger.info(f"Search documents added: {len(search_documents) if search_documents else 0}")
            
            return processed_doc
            
        except Exception as e:
            logger.error(f"Error processing document from {source}: {e}")
            observability.track_document_processing_error(source, str(e))
            raise
    
    def _initialize_section_patterns(self) -> Dict[str, List[str]]:
        """Initialize patterns for identifying financial document sections"""
        return {
            "10k_sections": [
                r"PART\s+I\s*ITEM\s+1[.\s]*BUSINESS",
                r"PART\s+I\s*ITEM\s+1A[.\s]*RISK\s+FACTORS",
                r"PART\s+I\s*ITEM\s+1B[.\s]*UNRESOLVED\s+STAFF\s+COMMENTS",
                r"PART\s+I\s*ITEM\s+2[.\s]*PROPERTIES",
                r"PART\s+I\s*ITEM\s+3[.\s]*LEGAL\s+PROCEEDINGS",
                r"PART\s+I\s*ITEM\s+4[.\s]*MINE\s+SAFETY\s+DISCLOSURES",
                r"PART\s+II\s*ITEM\s+5[.\s]*MARKET\s+FOR\s+REGISTRANT'S\s+COMMON\s+EQUITY",
                r"PART\s+II\s*ITEM\s+6[.\s]*SELECTED\s+FINANCIAL\s+DATA",
                r"PART\s+II\s*ITEM\s+7[.\s]*MANAGEMENT'S\s+DISCUSSION\s+AND\s+ANALYSIS",
                r"PART\s+II\s*ITEM\s+7A[.\s]*QUANTITATIVE\s+AND\s+QUALITATIVE\s+DISCLOSURES",
                r"PART\s+II\s*ITEM\s+8[.\s]*FINANCIAL\s+STATEMENTS\s+AND\s+SUPPLEMENTARY\s+DATA",
                r"PART\s+II\s*ITEM\s+9[.\s]*CHANGES\s+IN\s+AND\s+DISAGREEMENTS",
                r"PART\s+II\s*ITEM\s+9A[.\s]*CONTROLS\s+AND\s+PROCEDURES",
                r"PART\s+II\s*ITEM\s+9B[.\s]*OTHER\s+INFORMATION"
            ],
            "10q_sections": [
                r"PART\s+I\s*ITEM\s+1[.\s]*FINANCIAL\s+STATEMENTS",
                r"PART\s+I\s*ITEM\s+2[.\s]*MANAGEMENT'S\s+DISCUSSION\s+AND\s+ANALYSIS",
                r"PART\s+I\s*ITEM\s+3[.\s]*QUANTITATIVE\s+AND\s+QUALITATIVE\s+DISCLOSURES",
                r"PART\s+I\s*ITEM\s+4[.\s]*CONTROLS\s+AND\s+PROCEDURES",
                r"PART\s+II\s*ITEM\s+1[.\s]*LEGAL\s+PROCEEDINGS",
                r"PART\s+II\s*ITEM\s+1A[.\s]*RISK\s+FACTORS",
                r"PART\s+II\s*ITEM\s+2[.\s]*UNREGISTERED\s+SALES\s+OF\s+EQUITY\s+SECURITIES",
                r"PART\s+II\s*ITEM\s+3[.\s]*DEFAULTS\s+UPON\s+SENIOR\s+SECURITIES",
                r"PART\s+II\s*ITEM\s+4[.\s]*MINE\s+SAFETY\s+DISCLOSURES",
                r"PART\s+II\s*ITEM\s+5[.\s]*OTHER\s+INFORMATION",
                r"PART\s+II\s*ITEM\s+6[.\s]*EXHIBITS"
            ],
            "financial_statements": [
                r"CONSOLIDATED\s+BALANCE\s+SHEETS?",
                r"CONSOLIDATED\s+STATEMENTS?\s+OF\s+OPERATIONS",
                r"CONSOLIDATED\s+STATEMENTS?\s+OF\s+INCOME",
                r"CONSOLIDATED\s+STATEMENTS?\s+OF\s+COMPREHENSIVE\s+INCOME",
                r"CONSOLIDATED\s+STATEMENTS?\s+OF\s+CASH\s+FLOWS?",
                r"CONSOLIDATED\s+STATEMENTS?\s+OF\s+STOCKHOLDERS?\s+EQUITY",
                r"NOTES?\s+TO\s+CONSOLIDATED\s+FINANCIAL\s+STATEMENTS"
            ]
        }
    
    def _initialize_metrics_patterns(self) -> Dict[str, List[str]]:
        """Initialize patterns for extracting financial metrics"""
        return {
            "revenue_patterns": [
                r"(?:TOTAL\s+)?(?:NET\s+)?(?:REVENUES?|SALES?)[:\s]*\$?\s*([\d,]+(?:\.\d+)?)",
                r"(?:OPERATING\s+)?REVENUES?[:\s]*\$?\s*([\d,]+(?:\.\d+)?)",
            ],
            "income_patterns": [
                r"NET\s+INCOME[:\s]*\$?\s*([\d,]+(?:\.\d+)?)",
                r"(?:OPERATING\s+)?INCOME[:\s]*\$?\s*([\d,]+(?:\.\d+)?)",
                r"EARNINGS?\s+(?:PER\s+SHARE)?[:\s]*\$?\s*([\d,]+(?:\.\d+)?)"
            ],
            "asset_patterns": [
                r"TOTAL\s+ASSETS[:\s]*\$?\s*([\d,]+(?:\.\d+)?)",
                r"CURRENT\s+ASSETS[:\s]*\$?\s*([\d,]+(?:\.\d+)?)",
                r"CASH\s+AND\s+(?:CASH\s+)?EQUIVALENTS[:\s]*\$?\s*([\d,]+(?:\.\d+)?)"
            ],
            "liability_patterns": [
                r"TOTAL\s+LIABILITIES[:\s]*\$?\s*([\d,]+(?:\.\d+)?)",
                r"CURRENT\s+LIABILITIES[:\s]*\$?\s*([\d,]+(?:\.\d+)?)",
                r"LONG[- ]TERM\s+DEBT[:\s]*\$?\s*([\d,]+(?:\.\d+)?)"
            ]
        }
    
    def _generate_document_id(self, source: str, content: str) -> str:
        """Generate unique document ID based on source and content"""
        content_hash = hashlib.md5(content.encode()).hexdigest()[:12]
        source_hash = hashlib.md5(source.encode()).hexdigest()[:8]
        return f"doc_{source_hash}_{content_hash}"
    
    async def _extract_comprehensive_financial_info(self, extracted_content: Dict, source: str) -> Dict[str, Any]:
        """Enhanced financial information extraction with comprehensive metadata"""
        content = extracted_content["content"]
        
        financial_info = {
            "document_type": "unknown",
            "company_name": None,
            "cik": None,
            "ticker_symbol": None,
            "filing_date": None,
            "period_end_date": None,
            "fiscal_year": None,
            "fiscal_quarter": None,
            "amendment": False,
            "key_metrics": [],
            "sections": [],
            "page_count": extracted_content.get("pages", 0),
            "has_tables": len(extracted_content.get("tables", [])) > 0,
            "has_key_value_pairs": len(extracted_content.get("key_value_pairs", {})) > 0
        }
        
        try:
            content_upper = content.upper()
            if "FORM 10-K" in content_upper or "10-K" in content_upper:
                financial_info["document_type"] = "10-K"
                if "/A" in content_upper or "AMENDMENT" in content_upper:
                    financial_info["amendment"] = True
            elif "FORM 10-Q" in content_upper or "10-Q" in content_upper:
                financial_info["document_type"] = "10-Q"
                if "/A" in content_upper or "AMENDMENT" in content_upper:
                    financial_info["amendment"] = True
            elif "FORM 8-K" in content_upper:
                financial_info["document_type"] = "8-K"
            elif "PROXY STATEMENT" in content_upper or "DEF 14A" in content_upper:
                financial_info["document_type"] = "proxy-statement"
            elif "ANNUAL REPORT" in content_upper:
                financial_info["document_type"] = "annual-report"
            elif "EARNINGS" in content_upper:
                financial_info["document_type"] = "earnings-report"
            
            company_patterns = [
                r"COMPANY\s+NAME[:\s]+([A-Z][A-Za-z\s&,\.Inc]+?)(?:\n|$)",
                r"REGISTRANT[:\s]+([A-Z][A-Za-z\s&,\.Inc]+?)(?:\n|$)",
                r"^([A-Z][A-Za-z\s&,\.Inc]+?)\s+(?:FORM|10-[KQ])",
                r"COMMISSION\s+FILE\s+NUMBER[:\s]+[\d-]+\s*\n\s*([A-Z][A-Za-z\s&,\.Inc]+)"
            ]
            
            for pattern in company_patterns:
                match = re.search(pattern, content[:3000], re.MULTILINE | re.IGNORECASE)
                if match:
                    company_name = match.group(1).strip()
                    company_name = re.sub(r'\s+(INC\.?|CORP\.?|LLC\.?|LTD\.?)$', '', company_name, flags=re.IGNORECASE)
                    financial_info["company_name"] = company_name
                    break
            
            cik_match = re.search(r"CENTRAL\s+INDEX\s+KEY[:\s]+(\d+)", content[:2000], re.IGNORECASE)
            if cik_match:
                financial_info["cik"] = cik_match.group(1)
            
            ticker_patterns = [
                r"TRADING\s+SYMBOL[:\s]+([A-Z]{1,5})",
                r"TICKER\s+SYMBOL[:\s]+([A-Z]{1,5})",
                r"NASDAQ[:\s]+([A-Z]{1,5})",
                r"NYSE[:\s]+([A-Z]{1,5})"
            ]
            
            for pattern in ticker_patterns:
                match = re.search(pattern, content[:2000], re.IGNORECASE)
                if match:
                    financial_info["ticker_symbol"] = match.group(1)
                    break
            
            date_patterns = [
                r"FILING\s+DATE[:\s]+(\d{4}-\d{2}-\d{2})",
                r"DATE\s+OF\s+REPORT[:\s]+(\d{1,2}/\d{1,2}/\d{4})",
                r"PERIOD\s+END\s+DATE[:\s]+(\d{1,2}/\d{1,2}/\d{4})",
                r"(\d{4}-\d{2}-\d{2})"
            ]
            
            for pattern in date_patterns:
                match = re.search(pattern, content[:2000], re.IGNORECASE)
                if match:
                    financial_info["filing_date"] = match.group(1)
                    break
            
            period_patterns = [
                r"(?:FOR\s+THE\s+)?(?:QUARTER|PERIOD)\s+ENDED?\s+([A-Z]+\s+\d{1,2},\s+\d{4})",
                r"(?:FOR\s+THE\s+)?(?:YEAR)\s+ENDED?\s+([A-Z]+\s+\d{1,2},\s+\d{4})",
                r"PERIOD\s+END\s+DATE[:\s]+(\d{1,2}/\d{1,2}/\d{4})"
            ]
            
            for pattern in period_patterns:
                match = re.search(pattern, content[:2000], re.IGNORECASE)
                if match:
                    financial_info["period_end_date"] = match.group(1)
                    break
            
            fiscal_year_match = re.search(r"FISCAL\s+YEAR[:\s]+(\d{4})", content[:3000], re.IGNORECASE)
            if fiscal_year_match:
                financial_info["fiscal_year"] = fiscal_year_match.group(1)
            
            quarter_match = re.search(r"(?:FIRST|SECOND|THIRD|FOURTH|Q[1-4])\s+QUARTER", content[:2000], re.IGNORECASE)
            if quarter_match:
                quarter_text = quarter_match.group(0).upper()
                if "FIRST" in quarter_text or "Q1" in quarter_text:
                    financial_info["fiscal_quarter"] = "Q1"
                elif "SECOND" in quarter_text or "Q2" in quarter_text:
                    financial_info["fiscal_quarter"] = "Q2"
                elif "THIRD" in quarter_text or "Q3" in quarter_text:
                    financial_info["fiscal_quarter"] = "Q3"
                elif "FOURTH" in quarter_text or "Q4" in quarter_text:
                    financial_info["fiscal_quarter"] = "Q4"
            
            doc_type = financial_info["document_type"]
            if doc_type in ["10-K", "10-Q"]:
                section_patterns = self.financial_section_patterns.get(f"{doc_type.lower()}_sections", [])
                found_sections = []
                
                for pattern in section_patterns:
                    if re.search(pattern, content_upper):
                        section_name = pattern.split(r'\s+')[-1].lower().replace(r'\s+', '_')
                        found_sections.append(section_name)
                
                financial_info["sections"] = found_sections
            
            fs_patterns = self.financial_section_patterns.get("financial_statements", [])
            financial_statements = []
            for pattern in fs_patterns:
                if re.search(pattern, content_upper):
                    stmt_name = pattern.replace(r'\s+', '_').replace(r'\?', '').lower()
                    financial_statements.append(stmt_name)
            
            financial_info["financial_statements"] = financial_statements
            
        except Exception as e:
            logger.error(f"Error extracting comprehensive financial information: {e}")
        
        return financial_info
    
    async def _create_financial_chunks(self, content: str, document_id: str, 
                                     metadata: Dict) -> List[DocumentChunk]:
        """Create chunks optimized for financial document content"""
        chunks = []
        
        sections = self._split_into_sections(content)
        
        chunk_index = 0
        for section_name, section_content in sections.items():
            section_chunks = self._split_section_into_chunks(
                section_content, 
                settings.MAX_CHUNK_SIZE,
                settings.CHUNK_OVERLAP
            )
            
            for i, chunk_content in enumerate(section_chunks):
                chunk_id = f"{document_id}_chunk_{chunk_index}"
                
                chunk_metadata = {
                    **metadata,
                    "chunk_index": chunk_index,
                    "section": section_name,
                    "section_chunk_index": i,
                    "total_section_chunks": len(section_chunks)
                }
                
                chunk = DocumentChunk(
                    chunk_id=chunk_id,
                    content=chunk_content.strip(),
                    metadata=chunk_metadata
                )
                
                chunks.append(chunk)
                chunk_index += 1
        
        logger.info(f"Created {len(chunks)} chunks for document {document_id}")
        return chunks
    
    def _split_into_sections(self, content: str) -> Dict[str, str]:
        """Split document content into logical sections"""
        sections = {"main": content}  # Default fallback
        
        section_headers = [
            r"PART\s+[IVX]+[.\s]*([A-Z][A-Z\s,&]+)",
            r"ITEM\s+\d+[A-Z]*[.\s]*([A-Z][A-Z\s,&]+)",
            r"^([A-Z][A-Za-z\s,&]{10,})\s*$",  # All caps headers
            r"^\d+\.\s*([A-Z][A-Za-z\s,&]+)$"  # Numbered sections
        ]
        
        try:
            current_section = "introduction"
            current_content = []
            sections = {}
            
            lines = content.split('\n')
            
            for line in lines:
                line = line.strip()
                if not line:
                    current_content.append(line)
                    continue
                
                is_header = False
                for pattern in section_headers:
                    match = re.match(pattern, line, re.IGNORECASE)
                    if match and len(line) < 100:  # Reasonable header length
                        if current_content:
                            sections[current_section] = '\n'.join(current_content)
                        
                        current_section = match.group(1).lower().replace(' ', '_')
                        current_content = []
                        is_header = True
                        break
                
                if not is_header:
                    current_content.append(line)
            
            if current_content:
                sections[current_section] = '\n'.join(current_content)
            
            if len(sections) <= 1:
                sections = {"main": content}
                
        except Exception as e:
            logger.error(f"Error splitting into sections: {e}")
            sections = {"main": content}
        
        return sections
    
    def _split_section_into_chunks(self, content: str, max_size: int, overlap: int) -> List[str]:
        """Split a section into smaller chunks with overlap"""
        if len(content) <= max_size:
            return [content]
        
        chunks = []
        start = 0
        
        while start < len(content):
            end = start + max_size
            
            if end < len(content):
                sentence_end = content.rfind('.', start + max_size - 200, end)
                if sentence_end > start:
                    end = sentence_end + 1
                else:
                    para_break = content.rfind('\n\n', start, end)
                    if para_break > start:
                        end = para_break
            
            chunk = content[start:end].strip()
            if chunk:
                chunks.append(chunk)
            
            start = max(start + 1, end - overlap)
            
            if start >= len(content):
                break
        
        return chunks
    
    async def _parse_financial_document_structure(self, extracted_content: Dict, financial_info: Dict) -> Dict:
        """Parse the hierarchical structure of financial documents"""
        content = extracted_content["content"]
        tables = extracted_content.get("tables", [])
        
        structure = {
            "sections": [],
            "tables": [],
            "footnotes": [],
            "key_value_pairs": extracted_content.get("key_value_pairs", {})
        }
        
        try:
            doc_type = financial_info.get("document_type", "unknown")
            if doc_type in ["10-K", "10-Q"]:
                structure["sections"] = await self._parse_sec_filing_sections(content, doc_type)
            else:
                structure["sections"] = await self._parse_generic_sections(content)
            
            structure["tables"] = await self._parse_financial_tables(tables, content)
            
            structure["footnotes"] = await self._extract_footnotes(content)
            
        except Exception as e:
            logger.error(f"Error parsing document structure: {e}")
        
        return structure
    
    async def _parse_sec_filing_sections(self, content: str, doc_type: str) -> List[Dict]:
        """Parse SEC filing sections with proper hierarchy"""
        sections = []
        section_patterns = self.financial_section_patterns.get(f"{doc_type.lower()}_sections", [])
        
        current_section = None
        current_content = []
        current_section_start = 0
        lines = content.split('\n')
        
        for i, line in enumerate(lines):
            line_upper = line.strip().upper()
            
            section_found = False
            for pattern in section_patterns:
                if re.search(pattern, line_upper):
                    if current_section:
                        sections.append({
                            "title": current_section,
                            "content": '\n'.join(current_content),
                            "start_line": current_section_start,
                            "end_line": i,
                            "section_type": self._classify_section_type(current_section)
                        })
                    
                    current_section = line.strip()
                    current_section_start = i
                    current_content = []
                    section_found = True
                    break
            
            if not section_found and current_section:
                current_content.append(line)
        
        if current_section and current_content:
            sections.append({
                "title": current_section,
                "content": '\n'.join(current_content),
                "start_line": current_section_start,
                "end_line": len(lines),
                "section_type": self._classify_section_type(current_section)
            })
        
        return sections
    
    async def _parse_generic_sections(self, content: str) -> List[Dict]:
        """Parse generic document sections"""
        sections = []
        
        # Simple section detection for non-SEC documents
        section_patterns = [
            r"^([A-Z][A-Z\s,&]{10,})\s*$",  # All caps headers
            r"^\d+\.\s*([A-Z][A-Za-z\s,&]+)$"  # Numbered sections
        ]
        
        current_section = "Introduction"
        current_content = []
        lines = content.split('\n')
        
        for i, line in enumerate(lines):
            line_stripped = line.strip()
            
            is_header = False
            for pattern in section_patterns:
                match = re.match(pattern, line_stripped)
                if match and len(line_stripped) < 100:
                    if current_content:
                        sections.append({
                            "title": current_section,
                            "content": '\n'.join(current_content),
                            "start_line": 0 if not sections else sections[-1]["end_line"],
                            "end_line": i,
                            "section_type": "generic"
                        })
                    
                    current_section = match.group(1) if match.groups() else line_stripped
                    current_content = []
                    is_header = True
                    break
            
            if not is_header:
                current_content.append(line)
        
        if current_content:
            sections.append({
                "title": current_section,
                "content": '\n'.join(current_content),
                "start_line": 0 if not sections else sections[-1]["end_line"],
                "end_line": len(lines),
                "section_type": "generic"
            })
        
        return sections
    
    def _classify_section_type(self, section_title: str) -> str:
        """Classify the type of section based on title"""
        title_upper = section_title.upper()
        
        if "BUSINESS" in title_upper:
            return "business_overview"
        elif "RISK" in title_upper:
            return "risk_factors"
        elif "FINANCIAL STATEMENTS" in title_upper:
            return "financial_statements"
        elif "MANAGEMENT" in title_upper and "DISCUSSION" in title_upper:
            return "md_and_a"
        elif "LEGAL" in title_upper:
            return "legal_proceedings"
        elif "CONTROLS" in title_upper:
            return "controls_procedures"
        elif "PROPERTIES" in title_upper:
            return "properties"
        else:
            return "other"
    
    async def _parse_financial_tables(self, tables: List, content: str) -> List[Dict]:
        """Parse financial tables with enhanced metadata"""
        parsed_tables = []
        
        for i, table in enumerate(tables):
            try:
                table_data = {
                    "table_id": f"table_{i}",
                    "title": self._extract_table_title(table, content),
                    "rows": [],
                    "headers": [],
                    "financial_type": self._classify_table_type(table),
                    "page_number": getattr(table, 'page_number', 0),
                    "cell_count": len(getattr(table, 'cells', [])),
                    "bounding_box": getattr(table, 'bounding_box', None)
                }
                
                # Extract table structure
                if hasattr(table, 'cells'):
                    cells_by_row = {}
                    headers = []
                    
                    for cell in table.cells:
                        row_idx = cell.row_index
                        col_idx = cell.column_index
                        
                        if row_idx not in cells_by_row:
                            cells_by_row[row_idx] = {}
                        
                        cells_by_row[row_idx][col_idx] = cell.content
                        
                        if row_idx == 0:
                            headers.append(cell.content)
                    
                    table_data["headers"] = headers
                    
                    for row_idx in sorted(cells_by_row.keys()):
                        row_cells = cells_by_row[row_idx]
                        row_data = [row_cells.get(col_idx, "") for col_idx in sorted(row_cells.keys())]
                        table_data["rows"].append(row_data)
                
                parsed_tables.append(table_data)
                
            except Exception as e:
                logger.error(f"Error parsing table {i}: {e}")
        
        return parsed_tables
    
    def _extract_table_title(self, table, content: str) -> str:
        """Extract title for a financial table"""
        return f"Financial Table"
    
    def _classify_table_type(self, table) -> str:
        """Classify the type of financial table"""
        if hasattr(table, 'cells'):
            table_text = ' '.join([cell.content for cell in table.cells]).upper()
            
            if "BALANCE SHEET" in table_text:
                return "balance_sheet"
            elif "INCOME" in table_text or "OPERATIONS" in table_text:
                return "income_statement"
            elif "CASH FLOW" in table_text:
                return "cash_flow"
            elif "EQUITY" in table_text:
                return "equity_statement"
            elif any(term in table_text for term in ["REVENUE", "SALES", "INCOME"]):
                return "financial_performance"
            else:
                return "other_financial"
        
        return "unknown"
    
    async def _extract_footnotes(self, content: str) -> List[Dict]:
        """Extract footnotes with enhanced metadata"""
        footnotes = []
        
        footnote_patterns = [
            r"^\(\d+\)\s+(.+?)(?=^\(\d+\)|$)",  # (1) footnote format
            r"^\d+\.\s+(.+?)(?=^\d+\.|$)",      # 1. footnote format
            r"^\*\s+(.+?)(?=^\*|$)",            # * footnote format
        ]
        
        for pattern_idx, pattern in enumerate(footnote_patterns):
            matches = re.findall(pattern, content, re.MULTILINE | re.DOTALL)
            
            for match_idx, match in enumerate(matches):
                footnote = {
                    "footnote_id": f"footnote_{pattern_idx}_{match_idx}",
                    "content": match.strip(),
                    "pattern_type": pattern_idx,
                    "length": len(match.strip()),
                    "contains_financial_data": self._contains_financial_data(match)
                }
                footnotes.append(footnote)
        
        return footnotes[:50]  # Limit to first 50 footnotes
    
    def _contains_financial_data(self, text: str) -> bool:
        """Check if text contains financial data"""
        financial_indicators = [
            r'\$[\d,]+', r'[\d,]+\s*million', r'[\d,]+\s*billion',
            r'[\d.]+%', r'basis\s+points', r'revenue', r'income',
            r'assets', r'liabilities', r'equity'
        ]
        
        text_lower = text.lower()
        return any(re.search(pattern, text_lower) for pattern in financial_indicators)
    
    async def _create_hierarchical_financial_chunks(self, document_structure: Dict, 
                                                  document_id: str, metadata: Dict) -> List[DocumentChunk]:
        """Create hierarchical chunks with proper citation tracking"""
        chunks = []
        chunk_index = 0
        
        for section in document_structure.get("sections", []):
            section_chunks = await self._chunk_section_hierarchically(
                section, document_id, chunk_index, metadata
            )
            chunks.extend(section_chunks)
            chunk_index += len(section_chunks)
        
        for table in document_structure.get("tables", []):
            table_chunk = await self._create_table_chunk(
                table, document_id, chunk_index, metadata
            )
            chunks.append(table_chunk)
            chunk_index += 1
        
        for footnote in document_structure.get("footnotes", []):
            footnote_chunk = await self._create_footnote_chunk(
                footnote, document_id, chunk_index, metadata
            )
            chunks.append(footnote_chunk)
            chunk_index += 1
        
        logger.info(f"Created {len(chunks)} hierarchical chunks for document {document_id}")
        return chunks
    
    async def _chunk_section_hierarchically(self, section: Dict, document_id: str, 
                                          start_index: int, metadata: Dict) -> List[DocumentChunk]:
        """Chunk a section hierarchically with proper overlap"""
        chunks = []
        section_content = section["content"]
        
        if len(section_content) <= settings.MAX_CHUNK_SIZE:
            chunk = DocumentChunk(
                chunk_id=f"{document_id}_chunk_{start_index}",
                content=section_content,
                metadata={
                    **metadata,
                    "chunk_index": start_index,
                    "section_title": section["title"],
                    "section_type": section["section_type"],
                    "hierarchical_level": 1,
                    "start_line": section.get("start_line", 0),
                    "end_line": section.get("end_line", 0)
                },
                citation_info={
                    "section": section["title"],
                    "page_range": f"{section.get('start_line', 0)}-{section.get('end_line', 0)}",
                    "document_type": metadata.get("document_type", "unknown")
                }
            )
            chunks.append(chunk)
        else:
            section_chunks = self._split_with_overlap(
                section_content, settings.MAX_CHUNK_SIZE, settings.CHUNK_OVERLAP
            )
            
            for i, chunk_content in enumerate(section_chunks):
                chunk = DocumentChunk(
                    chunk_id=f"{document_id}_chunk_{start_index + i}",
                    content=chunk_content,
                    metadata={
                        **metadata,
                        "chunk_index": start_index + i,
                        "section_title": section["title"],
                        "section_type": section["section_type"],
                        "section_chunk_index": i,
                        "total_section_chunks": len(section_chunks),
                        "hierarchical_level": 2,
                        "start_line": section.get("start_line", 0),
                        "end_line": section.get("end_line", 0)
                    },
                    citation_info={
                        "section": section["title"],
                        "subsection": f"Part {i+1} of {len(section_chunks)}",
                        "page_range": f"{section.get('start_line', 0)}-{section.get('end_line', 0)}",
                        "document_type": metadata.get("document_type", "unknown")
                    }
                )
                chunks.append(chunk)
        
        return chunks
    
    async def _create_table_chunk(self, table: Dict, document_id: str, 
                                chunk_index: int, metadata: Dict) -> DocumentChunk:
        """Create a specialized chunk for financial tables"""
        table_content = self._format_table_content(table)
        
        return DocumentChunk(
            chunk_id=f"{document_id}_table_{chunk_index}",
            content=table_content,
            metadata={
                **metadata,
                "chunk_index": chunk_index,
                "chunk_type": "table",
                "table_id": table["table_id"],
                "table_title": table.get("title", ""),
                "financial_type": table.get("financial_type", "unknown"),
                "hierarchical_level": 0,  # Tables are top-level important
                "page_number": table.get("page_number", 0),
                "cell_count": table.get("cell_count", 0)
            },
            citation_info={
                "table_title": table.get("title", "Financial Table"),
                "table_type": table.get("financial_type", "unknown"),
                "page_number": table.get("page_number", 0),
                "document_type": metadata.get("document_type", "unknown")
            }
        )
    
    async def _create_footnote_chunk(self, footnote: Dict, document_id: str, 
                                   chunk_index: int, metadata: Dict) -> DocumentChunk:
        """Create a specialized chunk for footnotes"""
        return DocumentChunk(
            chunk_id=f"{document_id}_footnote_{chunk_index}",
            content=footnote["content"],
            metadata={
                **metadata,
                "chunk_index": chunk_index,
                "chunk_type": "footnote",
                "footnote_id": footnote["footnote_id"],
                "hierarchical_level": 3,  # Footnotes are detail-level
                "contains_financial_data": footnote.get("contains_financial_data", False),
                "footnote_length": footnote.get("length", 0)
            },
            citation_info={
                "footnote_id": footnote["footnote_id"],
                "citation_context": "footnote",
                "document_type": metadata.get("document_type", "unknown")
            }
        )
    
    def _format_table_content(self, table: Dict) -> str:
        """Format table content for text processing"""
        content_parts = []
        
        if table.get("title"):
            content_parts.append(f"Table: {table['title']}")
        
        headers = table.get("headers", [])
        if headers:
            content_parts.append("Headers: " + " | ".join(headers))
        
        rows = table.get("rows", [])
        for i, row in enumerate(rows[:10]):  # Limit to first 10 rows
            if i == 0 and headers:  # Skip header row if already processed
                continue
            row_text = " | ".join(str(cell) for cell in row)
            content_parts.append(f"Row {i}: {row_text}")
        
        if len(rows) > 10:
            content_parts.append(f"... and {len(rows) - 10} more rows")
        
        return "\n".join(content_parts)
    
    def _split_with_overlap(self, text: str, max_size: int, overlap: int) -> List[str]:
        """Split text with specified overlap, respecting sentence boundaries"""
        if len(text) <= max_size:
            return [text]
        
        chunks = []
        start = 0
        
        while start < len(text):
            end = start + max_size
            
            if end < len(text):
                sentence_end = text.rfind('.', start + max_size - 200, end)
                if sentence_end > start:
                    end = sentence_end + 1
                else:
                    para_end = text.rfind('\n\n', start, end)
                    if para_end > start:
                        end = para_end
            
            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)
            
            start = max(start + 1, end - overlap)
            
            if start >= len(text):
                break
        
        return chunks
    
    async def _extract_key_financial_metrics(self, content: str, financial_info: Dict) -> List[Dict]:
        """Extract key financial metrics from document content"""
        metrics = []
        
        try:
            for pattern in self.financial_metrics_patterns["revenue_patterns"]:
                matches = re.finditer(pattern, content, re.IGNORECASE)
                for match in matches:
                    metrics.append({
                        "metric_type": "revenue",
                        "value": match.group(1),
                        "context": content[max(0, match.start()-100):match.end()+100],
                        "pattern_used": pattern
                    })
            
            for pattern in self.financial_metrics_patterns["income_patterns"]:
                matches = re.finditer(pattern, content, re.IGNORECASE)
                for match in matches:
                    metrics.append({
                        "metric_type": "income",
                        "value": match.group(1),
                        "context": content[max(0, match.start()-100):match.end()+100],
                        "pattern_used": pattern
                    })
            
            for pattern in self.financial_metrics_patterns["asset_patterns"]:
                matches = re.finditer(pattern, content, re.IGNORECASE)
                for match in matches:
                    metrics.append({
                        "metric_type": "assets",
                        "value": match.group(1),
                        "context": content[max(0, match.start()-100):match.end()+100],
                        "pattern_used": pattern
                    })
            
            for pattern in self.financial_metrics_patterns["liability_patterns"]:
                matches = re.finditer(pattern, content, re.IGNORECASE)
                for match in matches:
                    metrics.append({
                        "metric_type": "liabilities",
                        "value": match.group(1),
                        "context": content[max(0, match.start()-100):match.end()+100],
                        "pattern_used": pattern
                    })
            
        except Exception as e:
            logger.error(f"Error extracting financial metrics: {e}")
        
        return metrics[:100]  # Limit to first 100 metrics
    
    def _structure_to_dict(self, structure: Dict) -> Dict:
        """Convert document structure to dictionary format"""
        return {
            "sections": structure.get("sections", []),
            "tables": structure.get("tables", []),
            "footnotes": structure.get("footnotes", []),
            "key_value_pairs": structure.get("key_value_pairs", {}),
            "structure_stats": {
                "total_sections": len(structure.get("sections", [])),
                "total_tables": len(structure.get("tables", [])),
                "total_footnotes": len(structure.get("footnotes", [])),
                "has_key_value_pairs": len(structure.get("key_value_pairs", {})) > 0
            }
        }
    
    def _chunk_to_dict(self, chunk: DocumentChunk) -> Dict:
        """Convert DocumentChunk to dictionary with enhanced structure"""
        return {
            "chunk_id": chunk.chunk_id,
            "content": chunk.content,
            "metadata": chunk.metadata,
            "embedding": chunk.embedding,
            "citation_info": chunk.citation_info
        }
    
    async def _create_markdown_chunks(self, document_structure: Dict, document_id: str, metadata: Dict) -> List[DocumentChunk]:
        """
        Create chunks using markdown formatting for better content representation
        """
        chunks = []
        content = document_structure.get("extracted_content", {}).get("content", "")
        tables = document_structure.get("extracted_content", {}).get("tables", [])
        
        logger.info(f"DEBUG: Content length: {len(content)}")
        logger.info(f"DEBUG: Number of tables: {len(tables)}")
        logger.info(f"DEBUG: Content preview: {content[:200]}...")
        
        # Extract intelligent metadata using LLM
        logger.info(f"DEBUG: Starting intelligent metadata extraction...")
        chat_model = (metadata or {}).get('chat_model')
        intelligent_metadata = await self._extract_intelligent_metadata(content, metadata, chat_model)
        logger.info(f"DEBUG: Intelligent metadata extracted: {intelligent_metadata}")
        
        # Convert document to markdown format
        logger.info(f"DEBUG: Converting to markdown...")
        markdown_content = await self._convert_to_markdown(content, tables)
        logger.info(f"DEBUG: Markdown content length: {len(markdown_content)}")
        logger.info(f"DEBUG: Markdown preview: {markdown_content[:300]}...")
        
        # Split markdown into logical chunks
        logger.info(f"DEBUG: Splitting markdown content...")
        markdown_chunks = await self._split_markdown_content(markdown_content)
        logger.info(f"DEBUG: Split into {len(markdown_chunks)} preliminary chunks")
        
        for i, chunk_content in enumerate(markdown_chunks):
            if len(chunk_content.strip()) < 50:  # Skip very short chunks
                logger.info(f"DEBUG: Skipping chunk {i} - too short ({len(chunk_content)} chars)")
                continue
                
            # Extract page number from chunk content or context
            page_number = await self._extract_page_number_from_chunk(chunk_content, content)
            
            # Extract section type from chunk content
            section_type = await self._extract_section_type_from_chunk(chunk_content)
            
            chunk_metadata = {
                **intelligent_metadata,
                "chunk_index": i,
                "section_type": section_type,
                "page_number": page_number,
                "content_type": "markdown",
                "chunk_type": "text"
            }
            
            chunk = DocumentChunk(
                chunk_id=f"{document_id}_chunk_{i}",
                content=chunk_content,
                metadata=chunk_metadata,
                citation_info={
                    "page_number": page_number,
                    "section_type": section_type,
                    "document_type": intelligent_metadata.get("document_type"),
                    "company": intelligent_metadata.get("company_name"),
                    "filing_date": intelligent_metadata.get("filing_date")
                }
            )
            chunks.append(chunk)
            
        logger.info(f"DEBUG: Final chunks created: {len(chunks)}")
        return chunks

    async def _extract_intelligent_metadata(self, content: str, existing_metadata: Dict, chat_model: str = None) -> Dict:
        """
        Use LLM to intelligently extract metadata from document content
        """
        try:
            logger.info(f"Starting intelligent metadata extraction using LLM...")
            
            # Use provided chat model or fall back to environment variable
            deployment_name = chat_model or settings.AZURE_OPENAI_DEPLOYMENT_NAME
            
            # Skip LLM extraction if deployment is not available, use basic extraction
            if not deployment_name or deployment_name == "":
                logger.warning("No Azure OpenAI deployment configured, skipping LLM metadata extraction")
                return self._extract_basic_metadata(content, existing_metadata)
            
            logger.info(f"DEBUG: Using deployment: {deployment_name}")
            logger.info(f"DEBUG: Content length for LLM: {len(content)}")
            logger.info(f"DEBUG: Content sample: {content[:500]}...")
            
            # Create a prompt for metadata extraction
            extraction_prompt = f"""
            Analyze the following financial document content and extract key metadata. 
            Return ONLY a JSON object with the following fields:
            - company_name: The exact company name from the document
            - document_type: Type of document (10-K, 10-Q, 8-K, Annual Report, etc.)
            - filing_date: Filing date in YYYY-MM-DD format if available
            - fiscal_year: Fiscal year if mentioned
            - ticker_symbol: Stock ticker symbol if mentioned
            
            Document content (first 2000 characters):
            {content[:2000]}
            
            JSON:
            """
            
            logger.info(f"Calling Azure OpenAI for metadata extraction...")
            response = await self.azure_manager.openai_client.chat.completions.create(
                model=deployment_name,  # Use the provided deployment name
                messages=[
                    {"role": "system", "content": "You are an expert financial document analyzer. Extract metadata accurately and return only valid JSON."},
                    {"role": "user", "content": extraction_prompt}
                ],
                temperature=0.1,
                max_tokens=500
            )
            logger.info(f"LLM response received for metadata extraction")
            
            # Parse the LLM response
            llm_metadata = {}
            try:
                import json
                llm_response = response.choices[0].message.content.strip()
                logger.info(f"DEBUG: Raw LLM response: {llm_response}")
                
                # Remove any markdown formatting
                if llm_response.startswith("```json"):
                    llm_response = llm_response[7:-3]
                elif llm_response.startswith("```"):
                    llm_response = llm_response[3:-3]
                
                llm_metadata = json.loads(llm_response)
                logger.info(f"LLM extracted metadata: {llm_metadata}")
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse LLM metadata response: {e}")
                logger.warning(f"DEBUG: Problematic response was: {llm_response}")
                llm_metadata = {}
            
            # Combine with existing metadata, preferring LLM results for accuracy
            final_metadata = {**existing_metadata}
            logger.info(f"DEBUG: Starting metadata: {existing_metadata}")
            
            # Update with LLM extracted data if available and valid
            if llm_metadata.get("company_name") and llm_metadata["company_name"] != "N/A":
                final_metadata["company_name"] = llm_metadata["company_name"]
                logger.info(f"DEBUG: Updated company_name from LLM: {llm_metadata['company_name']}")
            
            if llm_metadata.get("document_type") and llm_metadata["document_type"] != "N/A":
                final_metadata["document_type"] = llm_metadata["document_type"]
                logger.info(f"DEBUG: Updated document_type from LLM: {llm_metadata['document_type']}")
                
            if llm_metadata.get("ticker_symbol") and llm_metadata["ticker_symbol"] != "N/A":
                final_metadata["ticker_symbol"] = llm_metadata["ticker_symbol"]
                logger.info(f"DEBUG: Updated ticker_symbol from LLM: {llm_metadata['ticker_symbol']}")
                
            if llm_metadata.get("filing_date") and llm_metadata["filing_date"] != "N/A":
                try:
                    # Validate date format
                    from datetime import datetime
                    datetime.strptime(llm_metadata["filing_date"], "%Y-%m-%d")
                    final_metadata["filing_date"] = llm_metadata["filing_date"]
                    logger.info(f"DEBUG: Updated filing_date from LLM: {llm_metadata['filing_date']}")
                except ValueError:
                    logger.warning(f"Invalid date format from LLM: {llm_metadata['filing_date']}")
            
            logger.info(f"DEBUG: Final metadata: {final_metadata}")
            return final_metadata
            
            if llm_metadata.get("fiscal_year"):
                final_metadata["fiscal_year"] = llm_metadata["fiscal_year"]
                
            if llm_metadata.get("ticker_symbol"):
                final_metadata["ticker_symbol"] = llm_metadata["ticker_symbol"]
            
            return final_metadata
            
        except Exception as e:
            logger.error(f"Error in intelligent metadata extraction: {e}")
            logger.info("Falling back to basic metadata extraction")
            return self._extract_basic_metadata(content, existing_metadata)

    def _extract_basic_metadata(self, content: str, existing_metadata: Dict) -> Dict:
        """
        Extract basic metadata using pattern matching instead of LLM
        """
        try:
            logger.info("Extracting basic metadata using pattern matching...")
            
            final_metadata = {**existing_metadata}
            content_lower = content.lower()
            
            # Extract company name patterns
            company_patterns = [
                r'(?:company name|registrant|corporation|inc\.|corp\.|llc):?\s*([A-Z][A-Za-z\s&,.-]+?)(?:\n|$|,)',
                r'([A-Z][A-Za-z\s&,.-]+?)\s+(?:corporation|inc\.|corp\.|llc|company)',
                r'registrant[:\s]+([A-Z][A-Za-z\s&,.-]+?)(?:\n|$)',
            ]
            
            for pattern in company_patterns:
                match = re.search(pattern, content, re.IGNORECASE)
                if match:
                    company_name = match.group(1).strip()
                    if len(company_name) > 5 and len(company_name) < 100:  # Reasonable length
                        final_metadata["company_name"] = company_name
                        break
            
            # Extract document type
            doc_type_patterns = [
                r'form\s+(10-k|10-q|8-k|20-f)',
                r'annual report',
                r'quarterly report',
                r'proxy statement'
            ]
            
            for pattern in doc_type_patterns:
                match = re.search(pattern, content_lower)
                if match:
                    if hasattr(match, 'group') and match.group(1):
                        final_metadata["document_type"] = match.group(1).upper()
                    else:
                        final_metadata["document_type"] = match.group(0).title()
                    break
            
            # Extract filing date patterns
            date_patterns = [
                r'(?:filed|filing date|date filed)[:\s]+(\d{1,2}[/-]\d{1,2}[/-]\d{4})',
                r'(?:filed|filing date|date filed)[:\s]+(\d{4}-\d{2}-\d{2})',
                r'for the (?:fiscal )?year ended[:\s]+(\d{1,2}[/-]\d{1,2}[/-]\d{4})',
            ]
            
            for pattern in date_patterns:
                match = re.search(pattern, content_lower)
                if match:
                    date_str = match.group(1)
                    # Try to normalize the date format
                    try:
                        from datetime import datetime
                        if '/' in date_str:
                            parsed_date = datetime.strptime(date_str, '%m/%d/%Y')
                        elif '-' in date_str and len(date_str.split('-')[0]) == 4:
                            parsed_date = datetime.strptime(date_str, '%Y-%m-%d')
                        else:
                            continue
                        final_metadata["filing_date"] = parsed_date.strftime('%Y-%m-%d')
                        break
                    except ValueError:
                        continue
            
            # Extract ticker symbol
            ticker_patterns = [
                r'(?:trading symbol|ticker|symbol)[:\s]+([A-Z]{1,5})',
                r'nasdaq[:\s]+([A-Z]{1,5})',
                r'nyse[:\s]+([A-Z]{1,5})'
            ]
            
            for pattern in ticker_patterns:
                match = re.search(pattern, content, re.IGNORECASE)
                if match:
                    final_metadata["ticker_symbol"] = match.group(1).upper()
                    break
            
            logger.info(f"Basic metadata extracted: {list(final_metadata.keys())}")
            return final_metadata
            
        except Exception as e:
            logger.error(f"Error in basic metadata extraction: {e}")
            return existing_metadata

    async def _create_basic_chunks(self, content: str, document_id: str, metadata: Dict) -> List[DocumentChunk]:
        """
        Create basic text chunks as fallback when markdown chunking fails
        """
        logger.info(f"Creating basic chunks for document {document_id}")
        chunks = []
        
        # Simple text splitting approach
        max_chunk_size = 1500
        overlap = 200
        
        # Split text into sentences first
        sentences = re.split(r'[.!?]+', content)
        
        current_chunk = ""
        chunk_index = 0
        
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
                
            # If adding this sentence would exceed chunk size
            if len(current_chunk) + len(sentence) > max_chunk_size and current_chunk:
                # Create chunk
                chunk = DocumentChunk(
                    chunk_id=f"basic_chunk_{chunk_index}",
                    content=current_chunk.strip(),
                    metadata={
                        **metadata,
                        "chunk_index": chunk_index,
                        "section_type": "general",
                        "page_number": max(1, chunk_index // 3 + 1),  # Rough page estimation
                        "content_type": "text",
                        "chunk_type": "basic"
                    },
                    citation_info={
                        "page_number": max(1, chunk_index // 3 + 1),
                        "section_type": "general",
                        "document_type": metadata.get("document_type", "financial"),
                        "company": metadata.get("company_name", ""),
                    }
                )
                chunks.append(chunk)
                
                # Start new chunk with overlap
                if len(current_chunk) > overlap:
                    current_chunk = current_chunk[-overlap:] + " " + sentence
                else:
                    current_chunk = sentence
                chunk_index += 1
            else:
                current_chunk += " " + sentence
        
        # Add final chunk
        if current_chunk.strip():
            chunk = DocumentChunk(
                chunk_id=f"basic_chunk_{chunk_index}",
                content=current_chunk.strip(),
                metadata={
                    **metadata,
                    "chunk_index": chunk_index,
                    "section_type": "general",
                    "page_number": max(1, chunk_index // 3 + 1),
                    "content_type": "text",
                    "chunk_type": "basic"
                },
                citation_info={
                    "page_number": max(1, chunk_index // 3 + 1),
                    "section_type": "general",
                    "document_type": metadata.get("document_type", "financial"),
                    "company": metadata.get("company_name", ""),
                }
            )
            chunks.append(chunk)
        
        logger.info(f"Created {len(chunks)} basic chunks")
        return chunks

    async def _convert_to_markdown(self, content: str, tables: List) -> str:
        """
        Convert document content to markdown format with proper structure
        """
        try:
            logger.info(f"DEBUG: Converting content to markdown, length: {len(content)}")
            markdown_content = []
            
            # Split content into sections
            sections = self._identify_document_sections(content)
            logger.info(f"DEBUG: Identified {len(sections)} sections")
            
            for i, section in enumerate(sections):
                logger.info(f"DEBUG: Processing section {i}: {section.get('title', 'No title')[:50]}")
                # Add section header
                if section.get("title"):
                    level = section.get("level", 2)
                    markdown_content.append(f"{'#' * level} {section['title']}\n")
                
                # Add section content with proper formatting
                section_text = section.get("content", "")
                
                # Clean and format the text
                formatted_text = self._format_text_content(section_text)
                markdown_content.append(formatted_text)
                markdown_content.append("\n")
            
            # Add tables in markdown format
            logger.info(f"DEBUG: Processing {len(tables)} tables")
            for i, table in enumerate(tables):
                table_markdown = self._convert_table_to_markdown(table, i)
                if table_markdown:
                    markdown_content.append(table_markdown)
                    markdown_content.append("\n")
            
            final_markdown = "\n".join(markdown_content)
            logger.info(f"DEBUG: Final markdown length: {len(final_markdown)}")
            
            # If no sections were found, use the raw content as fallback
            if len(sections) == 0 and len(final_markdown.strip()) < 100:
                logger.warning("DEBUG: No sections found, using raw content")
                return content
            
            return final_markdown
            
        except Exception as e:
            logger.error(f"Error converting to markdown: {e}")
            # Fallback to original content
            return content

    def _identify_document_sections(self, content: str) -> List[Dict]:
        """
        Identify document sections using patterns and structure
        """
        sections = []
        
        # Common financial document section patterns
        section_patterns = [
            (r"PART\s+[IVX]+[.\s]*ITEM\s+\d+[A-Z]*[.\s]*([^.\n]+)", 2),
            (r"ITEM\s+\d+[A-Z]*[.\s]*([^.\n]+)", 2),
            (r"^([A-Z\s]{10,})\s*$", 1),  # All caps titles
            (r"^\d+\.\s*([^.\n]+)", 3),  # Numbered sections
        ]
        
        lines = content.split('\n')
        current_section = None
        current_content = []
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # Check if line matches a section pattern
            section_found = False
            for pattern, level in section_patterns:
                match = re.search(pattern, line, re.IGNORECASE)
                if match:
                    # Save previous section
                    if current_section:
                        current_section["content"] = "\n".join(current_content)
                        sections.append(current_section)
                    
                    # Start new section
                    current_section = {
                        "title": match.group(1).strip() if match.groups() else line,
                        "level": level,
                        "content": ""
                    }
                    current_content = []
                    section_found = True
                    break
            
            if not section_found:
                current_content.append(line)
        
        # Add final section
        if current_section:
            current_section["content"] = "\n".join(current_content)
            sections.append(current_section)
        
        # If no sections found, create a default section
        if not sections:
            sections.append({
                "title": "Document Content",
                "level": 1,
                "content": content
            })
        
        return sections

    def _format_text_content(self, text: str) -> str:
        """
        Format text content with proper markdown styling
        """
        # Clean up whitespace
        text = re.sub(r'\n\s*\n\s*\n', '\n\n', text)  # Remove excessive line breaks
        text = re.sub(r'[ \t]+', ' ', text)  # Normalize spaces
        
        # Format lists
        text = re.sub(r'^[\s]*[•·▪▫]\s*', '- ', text, flags=re.MULTILINE)
        text = re.sub(r'^[\s]*\d+\.\s*', '1. ', text, flags=re.MULTILINE)
        
        # Format emphasis (simple patterns)
        text = re.sub(r'\b([A-Z][A-Z\s]{5,})\b', r'**\1**', text)  # All caps to bold
        
        return text.strip()

    def _convert_table_to_markdown(self, table: Dict, table_index: int) -> str:
        """
        Convert table data to markdown table format
        """
        try:
            # Extract table data
            if hasattr(table, 'rows') and hasattr(table, 'headers'):
                headers = table.headers
                rows = table.rows
            elif isinstance(table, dict):
                headers = table.get("headers", [])
                rows = table.get("rows", [])
                if not headers and rows:
                    headers = [f"Column {i+1}" for i in range(len(rows[0]) if rows else 0)]
            else:
                return f"\n**Table {table_index + 1}**: {str(table)}\n"
            
            if not rows:
                return ""
            
            markdown_table = []
            
            # Add table title
            table_title = getattr(table, 'title', f"Table {table_index + 1}")
            markdown_table.append(f"\n### {table_title}\n")
            
            # Add headers
            if headers:
                header_row = "| " + " | ".join(str(h) for h in headers) + " |"
                separator = "| " + " | ".join("---" for _ in headers) + " |"
                markdown_table.append(header_row)
                markdown_table.append(separator)
            
            # Add data rows
            for row in rows:
                if row:  # Skip empty rows
                    row_data = "| " + " | ".join(str(cell) for cell in row) + " |"
                    markdown_table.append(row_data)
            
            return "\n".join(markdown_table) + "\n"
            
        except Exception as e:
            logger.warning(f"Error converting table {table_index} to markdown: {e}")
            return f"\n**Table {table_index + 1}**: [Table data could not be formatted]\n"

    async def _split_markdown_content(self, markdown_content: str) -> List[str]:
        """
        Split markdown content into appropriately sized chunks
        """
        chunks = []
        current_chunk = []
        current_size = 0
        max_chunk_size = 1500  # Characters per chunk
        
        logger.info(f"DEBUG: Splitting markdown content of length {len(markdown_content)}")
        
        lines = markdown_content.split('\n')
        logger.info(f"DEBUG: Split into {len(lines)} lines")
        
        for i, line in enumerate(lines):
            line_size = len(line)
            
            # If adding this line would exceed chunk size and we have content
            if current_size + line_size > max_chunk_size and current_chunk:
                chunk_content = '\n'.join(current_chunk).strip()
                if chunk_content:
                    chunks.append(chunk_content)
                    logger.info(f"DEBUG: Created chunk {len(chunks)}, size: {len(chunk_content)}")
                current_chunk = []
                current_size = 0
            
            current_chunk.append(line)
            current_size += line_size
        
        # Add final chunk
        if current_chunk:
            chunk_content = '\n'.join(current_chunk).strip()
            if chunk_content:
                chunks.append(chunk_content)
                logger.info(f"DEBUG: Created final chunk {len(chunks)}, size: {len(chunk_content)}")
        
        logger.info(f"DEBUG: Total chunks created: {len(chunks)}")
        return chunks

    async def _extract_page_number_from_chunk(self, chunk_content: str, full_content: str) -> int:
        """
        Extract accurate page number for a chunk using simple estimation
        """
        try:
            # Look for page references in the chunk
            page_patterns = [
                r'(?:page|p\.)\s*(\d+)',
                r'- (\d+) -',  # Common page number format
                r'Page\s+(\d+)',
            ]
            
            for pattern in page_patterns:
                matches = re.findall(pattern, chunk_content, re.IGNORECASE)
                if matches:
                    return int(matches[0])
            
            # If no direct page reference, estimate based on position in document
            chunk_position = full_content.find(chunk_content[:100])  # Find chunk in full content
            if chunk_position >= 0:
                # Rough estimation: 3000 characters per page
                estimated_page = max(1, chunk_position // 3000 + 1)
                return estimated_page
            
            return 1  # Default to page 1
            
        except Exception as e:
            logger.warning(f"Error extracting page number: {e}")
            return 1

    async def _extract_section_type_from_chunk(self, chunk_content: str) -> str:
        """
        Extract section type from chunk content using pattern matching
        """
        try:
            content_lower = chunk_content.lower()
            
            # Define section type patterns
            section_patterns = {
                "business": ["business", "company overview", "operations", "products and services"],
                "risk_factors": ["risk factors", "risks", "forward-looking statements"],
                "financial_statements": ["financial statements", "balance sheet", "income statement", "cash flow"],
                "md&a": ["management's discussion", "md&a", "financial condition", "results of operations"],
                "controls": ["controls and procedures", "internal controls", "disclosure controls"],
                "legal_proceedings": ["legal proceedings", "litigation", "legal matters"],
                "market_data": ["market for", "common equity", "stock performance"],
                "exhibits": ["exhibits", "signatures"],
                "executive_compensation": ["executive compensation", "compensation discussion"],
                "corporate_governance": ["corporate governance", "board of directors"]
            }
            
            for section_type, keywords in section_patterns.items():
                for keyword in keywords:
                    if keyword in content_lower:
                        return section_type
            
            # Check for ITEM patterns
            item_match = re.search(r'item\s+(\d+[a-z]*)', content_lower)
            if item_match:
                return f"item_{item_match.group(1)}"
            
            return "general"
            
        except Exception as e:
            logger.warning(f"Error extracting section type: {e}")
            return "general"
