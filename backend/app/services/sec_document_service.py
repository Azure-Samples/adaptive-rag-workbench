import asyncio
import logging
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, date
import hashlib
import json
from dataclasses import dataclass

# Configure edgartools
import edgar
edgar.set_identity("assistant@agenticrag.example.com")

from edgar import Company, Filing, get_company_facts
import re

from app.services.azure_services import AzureServiceManager
from app.core.config import settings
from app.services.document_processor import DocumentChunk
from app.services.credibility_assessor import CredibilityAssessor
from app.utils.chunker import DocumentChunker

logger = logging.getLogger(__name__)

@dataclass
class SECDocumentInfo:
    """Information about a SEC document"""
    ticker: str
    company_name: str
    cik: str
    form_type: str
    filing_date: date
    period_end_date: Optional[date]
    document_url: str
    accession_number: str
    file_size: Optional[int] = None

class SECDocumentService:
    """
    Service for retrieving and processing SEC documents using edgartools
    """
    
    def __init__(self, azure_manager: Optional[AzureServiceManager]):
        self.azure_manager = azure_manager
        # Only initialize Azure-dependent services if Azure manager is available
        if azure_manager:
            self.credibility_assessor = CredibilityAssessor(azure_manager)
        else:
            self.credibility_assessor = None
            logger.info("Running in SEC-only mode: Azure services not available")
        
        self.chunker = DocumentChunker(
            chunk_size=settings.chunk_size
        )
        
    async def search_companies(self, query: str) -> List[Dict[str, Any]]:
        """
        Search for companies by name or ticker and include available filings summary
        """
        try:
            logger.info(f"Searching for companies with query: {query}")
            
            # Use find_company to get the proper ticker
            try:
                from edgar import find_company, Company
                
                logger.info(f"Using find_company to search for: {query}")
                search_results = find_company(query)
                
                if search_results is not None and len(search_results) > 0:
                    # find_company returns a CompanySearchResults object
                    # Get the first (best) match - this is a Company object
                    best_match = search_results[0]
                    
                    # Get ticker from the Company object's tickers attribute
                    if hasattr(best_match, 'tickers') and best_match.tickers:
                        ticker = best_match.tickers[0]  # Get the first ticker
                        company_name = best_match.name
                        
                        logger.info(f"Found ticker via find_company: {query} -> {ticker} ({company_name})")
                        
                        # Use the Company object we already have
                        return await self._get_company_info(best_match, ticker)
                    else:
                        logger.warning(f"Company found but no tickers available: {best_match.name}")
                        
            except Exception as search_error:
                logger.warning(f"find_company failed for '{query}': {search_error}")
                
            # If find_company fails, try direct ticker lookup for common symbols
            logger.info(f"Trying fallback mapping for: {query}")
            name_to_ticker = {
                'apple': 'AAPL',
                'aaple': 'AAPL',  # Common typo
                'apple inc': 'AAPL', 
                'apple computer': 'AAPL',
                'apple inc.': 'AAPL',
                'microsoft': 'MSFT',
                'microsoft corp': 'MSFT',
                'microsoft corporation': 'MSFT',
                'amazon': 'AMZN',
                'amazon.com': 'AMZN',
                'amazon inc': 'AMZN',
                'amazon.com inc': 'AMZN',
                'google': 'GOOGL',
                'alphabet': 'GOOGL',
                'alphabet inc': 'GOOGL',
                'alphabet inc.': 'GOOGL',
                'tesla': 'TSLA',
                'tesla inc': 'TSLA',
                'tesla motors': 'TSLA',
                'tesla inc.': 'TSLA',
                'facebook': 'META',
                'meta': 'META',
                'meta platforms': 'META',
                'meta platforms inc': 'META',
                'nvidia': 'NVDA',
                'nvidia corp': 'NVDA',
                'nvidia corporation': 'NVDA',
                'netflix': 'NFLX',
                'oracle': 'ORCL',
                'oracle corp': 'ORCL',
                'oracle corporation': 'ORCL',
                'salesforce': 'CRM',
                'salesforce.com': 'CRM',
                'adobe': 'ADBE',
                'adobe inc': 'ADBE',
                'adobe systems': 'ADBE',
                'intel': 'INTC',
                'intel corp': 'INTC',
                'intel corporation': 'INTC',
                'ibm': 'IBM',
                'international business machines': 'IBM',
                'cisco': 'CSCO',
                'cisco systems': 'CSCO',
                'paypal': 'PYPL',
                'paypal holdings': 'PYPL'
            }
            
            query_lower = query.lower().strip()
            if query_lower in name_to_ticker:
                logger.info(f"Found fallback mapping: {query} -> {name_to_ticker[query_lower]}")
                company = Company(name_to_ticker[query_lower])
                return await self._get_company_info(company, name_to_ticker[query_lower])
            
            logger.warning(f"Company not found for query: {query}")
            return []
                
        except Exception as e:
            logger.error(f"Error searching companies: {e}")
            return []
                
    async def _get_company_info(self, company, ticker: str) -> List[Dict[str, Any]]:
        """
        Extract company information and filing summary
        """
        try:
            # Get recent filings to show available document types and years
            recent_filings = company.get_filings(form=['10-K', '10-Q', '8-K', '10-Q/A', '10-K/A']).head(50)
            
            # Organize filings by type and year
            filings_summary = {}
            available_years = set()
            
            for filing in recent_filings:
                form_type = filing.form
                filing_year = filing.filing_date.year
                available_years.add(filing_year)
                
                if form_type not in filings_summary:
                    filings_summary[form_type] = {
                        "count": 0,
                        "years": set(),
                        "latest_date": None
                    }
                
                filings_summary[form_type]["count"] += 1
                filings_summary[form_type]["years"].add(filing_year)
                
                if (filings_summary[form_type]["latest_date"] is None or 
                    filing.filing_date > filings_summary[form_type]["latest_date"]):
                    filings_summary[form_type]["latest_date"] = filing.filing_date
            
            # Convert sets to sorted lists for JSON serialization
            for form_type in filings_summary:
                filings_summary[form_type]["years"] = sorted(list(filings_summary[form_type]["years"]), reverse=True)
                if filings_summary[form_type]["latest_date"]:
                    filings_summary[form_type]["latest_date"] = filings_summary[form_type]["latest_date"].isoformat()
            
            company_info = {
                "ticker": ticker,
                "company_name": company.name,
                "cik": str(company.cik).zfill(10),  # Ensure CIK is 10 digits with leading zeros
                "industry": getattr(company, 'industry', 'Unknown'),
                "sic": str(getattr(company, 'sic', 'Unknown')),
                "entity_type": getattr(company, 'entity_type', 'Unknown'),
                "available_years": sorted(list(available_years), reverse=True),
                "available_forms": filings_summary,
                "total_filings": len(recent_filings)
            }
            
            logger.info(f"Found company: {company.name} with {len(recent_filings)} recent filings")
            return [company_info]
            
        except Exception as e:
            logger.error(f"Error getting company info: {e}")
            return []
    
    async def get_company_filings(
        self, 
        ticker: str, 
        form_types: List[str] = None, 
        limit: int = 20
    ) -> List[SECDocumentInfo]:
        """
        Get recent filings for a company
        """
        try:
            logger.info(f"Getting filings for {ticker}, forms: {form_types}")
            
            if form_types is None:
                form_types = ['10-K', '10-Q', '8-K']
            
            company = Company(ticker.upper())
            filings = company.get_filings(form=form_types).head(limit)
            
            documents = []
            for filing in filings:
                doc_info = SECDocumentInfo(
                    ticker=ticker.upper(),
                    company_name=company.name,
                    cik=str(company.cik),
                    form_type=filing.form,
                    filing_date=filing.filing_date,
                    period_end_date=getattr(filing, 'period_end_date', None),
                    document_url=getattr(filing, 'document_url', ''),
                    accession_number=filing.accession_number,
                    file_size=getattr(filing, 'size', None)                )
                documents.append(doc_info)
            
            logger.info(f"Found {len(documents)} filings for {ticker}")
            return documents            
        except Exception as e:
            logger.error(f"Error getting filings for {ticker}: {e}")
            return []
    
    async def retrieve_and_process_document(
        self, 
        ticker: str, 
        accession_number: str,
        document_id: Optional[str] = None,
        progress_callback=None) -> Dict[str, Any]:
        """
        Retrieve SEC document and process it into chunks using md2chunks
        """
        try:
            logger.info(f"Retrieving SEC document: {ticker} - {accession_number}")
            
            # Progress callback helper
            async def report_progress(percent: float, message: str):
                if progress_callback:
                    await progress_callback("processing", percent, message)
                logger.info(f"Progress: {percent:.1f}% - {message}")
            
            await report_progress(5.0, "Starting document retrieval")
            
            # Check if document already exists in the index (only if Azure services available)
            document_exists = False
            await self.azure_manager.ensure_search_index_exists()
            if self.azure_manager:
                document_exists = await self.azure_manager.check_document_exists(accession_number)
            if document_exists:
                logger.info(f"Document {accession_number} already exists in index, skipping processing")
                await report_progress(100.0, "Document already exists, skipping")
                return {
                    "document_id": f"{ticker}_{accession_number}",
                    "chunks_created": 0,
                    "metadata": {"status": "already_exists", "message": "Document already processed and indexed"},
                    "filing_info": {"ticker": ticker, "accession_number": accession_number},
                    "skipped": True
                }
            
            await report_progress(10.0, "Connecting to SEC EDGAR API")
            
            # Ensure we have a proper ticker symbol, not a company name
            actual_ticker = ticker.upper()
            
            # If the ticker looks like a company name, try to resolve it to a ticker
            if len(ticker) > 5 or ' ' in ticker:
                logger.info(f"Ticker '{ticker}' looks like a company name, resolving to ticker symbol")
                companies = await self.search_companies(ticker)
                if companies and len(companies) > 0:
                    actual_ticker = companies[0]['ticker']
                    logger.info(f"Resolved '{ticker}' to ticker '{actual_ticker}'")
                else:
                    raise ValueError(f"Could not resolve '{ticker}' to a valid ticker symbol")
            
            # Get the company and filing
            company = Company(actual_ticker)
            await report_progress(15.0, "Searching for filing in company records")
            
            # Try multiple approaches to find the filing
            filing = None
            
            # Method 1: Get all filings and search (default limit is 100)
            try:
                all_filings = company.get_filings()
                for f in all_filings:
                    if f.accession_number == accession_number:
                        filing = f
                        break
                logger.info(f"Found {len(all_filings)} recent filings, searching for {accession_number}")
            except Exception as e:
                logger.warning(f"Failed to get recent filings: {e}")
            
            # Method 2: If not found in recent filings, try with a larger limit  
            if not filing:
                try:
                    logger.info("Filing not found in recent filings, trying larger set...")
                    # get_filings() doesn't accept limit parameter, use head() instead
                    all_filings = company.get_filings().head(500)  # Get more filings
                    for f in all_filings:
                        if f.accession_number == accession_number:
                            filing = f
                            break
                    logger.info(f"Searched {len(all_filings)} filings for {accession_number}")
                except Exception as e:
                    logger.warning(f"Failed to get extended filings: {e}")
            
            # Method 3: Try direct filing retrieval
            if not filing:
                try:
                    # Try to find the filing by CIK and accession number directly
                    logger.info("Trying direct filing lookup by CIK...")
                    cik = company.cik
                    # This is a more robust approach - search through all available filings
                    all_filings = company.get_filings().head(1000)  # Get many more filings
                    for f in all_filings:
                        if f.accession_number == accession_number:
                            filing = f
                            break
                    if filing:
                        logger.info(f"Found filing via extended search: {accession_number}")
                except Exception as e:
                    logger.warning(f"Extended filing search failed: {e}")
                    logger.info(f"Found filing via direct retrieval: {accession_number}")
                except Exception as e:
                    logger.warning(f"Direct filing retrieval failed: {e}")
            
            if not filing:
                # Provide more helpful error message
                raise ValueError(f"Filing not found: {accession_number}. This filing may be too old, not exist, or the ticker '{ticker}' may not be associated with this accession number. Please verify the accession number and ticker are correct.")
            
            await report_progress(20.0, "Filing found, extracting metadata")
            
            # Extract document metadata
            metadata = {
                "ticker": actual_ticker,
                "company_name": company.name,
                "cik": str(company.cik).zfill(10),  # Ensure CIK is 10 digits with leading zeros
                "industry": getattr(company, 'industry', 'Unknown'),
                "sic": str(getattr(company, 'sic', 'Unknown')),
                "entity_type": getattr(company, 'entity_type', 'Unknown'),
                "form_type": filing.form,
                "filing_date": filing.filing_date.isoformat(),
                "period_end_date": filing.period_end_date.isoformat() if hasattr(filing, 'period_end_date') and filing.period_end_date else None,
                "accession_number": accession_number,
                "document_type": "SEC Filing",
                "source": "SEC EDGAR",
                "file_size": getattr(filing, 'size', None),
                "document_url": getattr(filing.document, 'url', '') if hasattr(filing, 'document') and filing.document else ''
            }
            
            logger.info(f"Document metadata: {metadata}")
            
            # Ensure document_id is set
            if not document_id:
                document_id = f"{actual_ticker}_{accession_number}_{filing.form}"
            
            await report_progress(30.0, "Downloading document content from SEC")
            
            # Get the document content
            # edgartools provides different ways to get content
            if hasattr(filing, 'text'):
                content = filing.text()
            elif hasattr(filing, 'html'):
                content = filing.html()
            else:
                content = str(filing)
            
            logger.info(f"Retrieved content length: {len(content)} characters")
            await report_progress(45.0, f"Downloaded document ({len(content):,} characters)")
            
            # Process the document into chunks
            await report_progress(50.0, "Processing document into chunks")
            chunks = await self._process_content_with_md2chunks(
                content, document_id, metadata, progress_callback
            )
            
            await report_progress(70.0, f"Generated {len(chunks)} chunks, starting embeddings")
            
            # Generate embeddings for chunks with progress updates
            await self._generate_embeddings_for_chunks(
                chunks, progress_callback
            )
            await report_progress(88.0, "Preparing documents for search index")
            # Store in Azure Search (only if Azure services available)
            search_documents = await self._prepare_search_documents(chunks)
            if search_documents and self.azure_manager:
                await report_progress(92.0, f"Indexing {len(search_documents)} documents")
                await self.azure_manager.add_documents_to_index(search_documents)
                logger.info(f"Added {len(search_documents)} documents to search index")
                await report_progress(98.0, "Successfully indexed all documents")
            elif search_documents:
                logger.info(f"Generated {len(search_documents)} search documents but Azure indexing not available")
                await report_progress(98.0, "Document processed but not indexed (Azure not available)")
            else:
                await report_progress(98.0, "No search documents generated")
            
            await report_progress(100.0, f"Completed processing {len(chunks)} chunks")
            logger.info(f"Successfully processed document with {len(chunks)} chunks")
            
            return {
                "document_id": document_id,
                "chunks_created": len(chunks),
                "metadata": metadata,
                "filing_info": {
                    "form_type": filing.form,
                    "filing_date": filing.filing_date.isoformat(),
                    "accession_number": accession_number,
                    "company_name": company.name,
                    "ticker": actual_ticker
                },
                "tokens_used": getattr(chunks[0], 'total_tokens_used', 0) if chunks else 0
            }
            
        except Exception as e:
            logger.error(f"Error retrieving and processing SEC document: {e}")
            # observability.record_error("sec_document_processing_error", str(e))
            raise
    
    async def _process_content_with_md2chunks(
        self, 
        content: str, 
        document_id: str, 
        metadata: Dict[str, Any],
        progress_callback=None
    ) -> List[DocumentChunk]:
        """
        Process content using md2chunks for intelligent chunking
        """
        try:
            logger.info(f"Processing content with md2chunks, length: {len(content)}")
            
            # Progress callback helper
            async def report_progress(percent: float, message: str):
                if progress_callback:
                    await progress_callback("processing", percent, message)
            
            await report_progress(50.0, "Cleaning and preparing content")
            
            # Clean and prepare content for markdown processing
            cleaned_content = self._clean_sec_content(content)
            
            # Convert to markdown if it's HTML
            if content.strip().startswith('<'):
                await report_progress(55.0, "Converting HTML to markdown")
                markdown_content = self._html_to_markdown(cleaned_content)
            else:
                markdown_content = cleaned_content
            
            logger.info(f"Markdown content length: {len(markdown_content)}")
            await report_progress(60.0, "Starting intelligent document chunking")
            
            # Use md2chunks to intelligently chunk the content
            try:
                # Configure chunker for financial documents
                chunks_data = self.chunker.chunk(
                    markdown_content,
                    chunk_size=settings.chunk_size,  # Use configured chunk size
                    overlap=settings.chunk_overlap,  # Use configured overlap
                    separator="\n\n"  # Prefer paragraph breaks
                )
                logger.info(f"md2chunks created {len(chunks_data)} chunks")
                await report_progress(65.0, f"Created {len(chunks_data)} intelligent chunks")
            except Exception as e:
                logger.warning(f"md2chunks failed: {e}, falling back to simple chunking")
                chunks_data = self._fallback_chunking(markdown_content)
                await report_progress(65.0, f"Created {len(chunks_data)} fallback chunks")
            
            await report_progress(68.0, "Converting chunks to document objects")
            
            # Convert to DocumentChunk objects
            document_chunks = []
            for i, chunk_data in enumerate(chunks_data):
                # Report progress every 10 chunks
                if i % 10 == 0 and progress_callback:
                    percent = 68.0 + (i / len(chunks_data)) * 2.0  # 68-70% range
                    await progress_callback("processing", percent, f"Processing chunk {i+1}/{len(chunks_data)}")
                
                # Handle md2chunks Attachment objects
                if hasattr(chunk_data, 'content'):
                    # This is an Attachment object from md2chunks
                    chunk_content = chunk_data.content
                    chunk_metadata = getattr(chunk_data, 'metadata', {}) if hasattr(chunk_data, 'metadata') else {}
                elif isinstance(chunk_data, dict):
                    # This is a dictionary (from fallback chunking)
                    chunk_content = chunk_data.get('content', str(chunk_data))
                    chunk_metadata = chunk_data.get('metadata', {})
                else:
                    # This is a string (from fallback chunking)
                    chunk_content = str(chunk_data)
                    chunk_metadata = {}
                
                if len(chunk_content.strip()) < 50:  # Skip very short chunks
                    continue
                  # Extract section information from chunk
                try:
                    section_info = self._extract_section_info(chunk_content)
                    if section_info is None:
                        section_info = {"section_type": "general"}
                except Exception as e:
                    logger.warning(f"Error extracting section info: {e}")
                    section_info = {"section_type": "general"}
                
                # Combine metadata
                final_metadata = {
                    **metadata,
                    **chunk_metadata,
                    "chunk_index": i,
                    "section_type": section_info.get("section_type", "general"),
                    "content_type": "markdown",
                    "chunk_method": "md2chunks"
                }
                
                chunk = DocumentChunk(
                    chunk_id=f"{document_id}_chunk_{i}",
                    content=chunk_content,
                    metadata=final_metadata,
                    citation_info={
                        "section_type": section_info.get("section_type"),
                        "document_type": metadata.get("form_type"),
                        "company": metadata.get("company_name"),
                        "ticker": metadata.get("ticker"),
                        "filing_date": metadata.get("filing_date")
                    }
                )
                document_chunks.append(chunk)
            
            logger.info(f"Created {len(document_chunks)} DocumentChunk objects")
            return document_chunks
            
        except Exception as e:
            logger.error(f"Error processing content with md2chunks: {e}")
            raise
    
    def _clean_sec_content(self, content: str) -> str:
        """
        Clean SEC document content for better processing
        """
        # Remove excessive whitespace
        content = re.sub(r'\s+', ' ', content)
        
        # Remove common SEC formatting artifacts
        content = re.sub(r'Table of Contents', '', content, flags=re.IGNORECASE)
        content = re.sub(r'\n\s*\n\s*\n', '\n\n', content)  # Multiple newlines to double
        
        # Remove page numbers and headers/footers patterns
        content = re.sub(r'\n\s*\d+\s*\n', '\n', content)  # Standalone page numbers
        content = re.sub(r'\n\s*-\s*\d+\s*-\s*\n', '\n', content)  # -1- style page numbers
        
        return content.strip()
    
    def _html_to_markdown(self, html_content: str) -> str:
        """
        Convert HTML SEC content to markdown
        """
        try:
            from markdownify import markdownify as md
            return md(html_content, heading_style="ATX")
        except ImportError:
            logger.warning("markdownify not available, using basic HTML cleaning")
            # Basic HTML tag removal
            import re
            content = re.sub(r'<[^>]+>', '', html_content)
            content = re.sub(r'&nbsp;', ' ', content)
            content = re.sub(r'&[a-zA-Z]+;', '', content)
            return content
    
    def _fallback_chunking(self, content: str) -> List[str]:
        """
        Simple fallback chunking if md2chunks fails
        """
        chunks = []
        lines = content.split('\n')
        current_chunk = []
        current_size = 0
        max_size = settings.chunk_size  # Use setting instead of hardcoded value
        
        for line in lines:
            if current_size + len(line) > max_size and current_chunk:
                chunks.append('\n'.join(current_chunk))
                current_chunk = []
                current_size = 0
            
            current_chunk.append(line)
            current_size += len(line)
        
        if current_chunk:
            chunks.append('\n'.join(current_chunk))
        
        return chunks
    
    def _extract_section_info(self, chunk_content: str) -> Dict[str, str]:
        """
        Extract section information from chunk content using targeted Item-based regex
        """
        import re
        
        # Primary regex to detect Item sections in SEC filings
        # Handles various formatting: "Item 1", "ITEM 1", with HTML entities, periods, etc.
        item_regex = re.compile(r'(>Item(\s|&#160;|&nbsp;)(1A|1B|1C|1D|2|3|4|5|6|7A|7|8|9A|9B|9C|9|10|11|12|13|14|15|16)\.?)|(ITEM\s+(1A|1B|1C|1D|2|3|4|5|6|7A|7|8|9A|9B|9C|9|10|11|12|13|14|15|16))', re.IGNORECASE)
        
        # Look for Item sections in the first 1000 characters of the chunk
        check_content = chunk_content[:1000]
        matches = list(item_regex.finditer(check_content))
        
        if matches:
            # Extract the item number from the first match
            match = matches[0]
            item_text = match.group(0)
            
            # Extract item number (handle both group patterns)
            item_num = None
            if match.group(3):  # From first pattern (>Item...)
                item_num = match.group(3)
            elif match.group(5):  # From second pattern (ITEM...)
                item_num = match.group(5)
            
            if item_num:
                # Map Item numbers to section types
                item_mapping = {
                    '1': 'business_overview',
                    '1A': 'risk_factors',
                    '1B': 'unresolved_staff_comments', 
                    '1C': 'cybersecurity',
                    '2': 'properties',
                    '3': 'legal_proceedings',
                    '4': 'mine_safety',
                    '5': 'market_for_equity',
                    '6': 'selected_financial_data',
                    '7': 'mda',
                    '7A': 'market_risk_disclosures',
                    '8': 'financial_statements',
                    '9': 'changes_in_accountants',
                    '9A': 'controls_and_procedures',
                    '9B': 'other_information',
                    '9C': 'disclosure_regarding_foreign_jurisdictions',
                    '10': 'directors_and_officers',
                    '11': 'executive_compensation',
                    '12': 'security_ownership',
                    '13': 'related_party_transactions',
                    '14': 'principal_accountant_fees',
                    '15': 'exhibits',
                    '16': 'form_10k_summary'
                }
                
                section_type = item_mapping.get(item_num, 'general')
                logger.debug(f"Detected Item {item_num} -> {section_type} from: {item_text[:50]}...")
                return {"section_type": section_type}
        
        # Secondary patterns for financial statements and other specific sections
        financial_patterns = {
            r'(?i)consolidated\s+balance\s+sheets?': 'balance_sheet',
            r'(?i)consolidated\s+statements?\s+of\s+(income|operations|earnings)': 'income_statement',
            r'(?i)consolidated\s+statements?\s+of\s+cash\s+flows?': 'cash_flow',
            r'(?i)consolidated\s+statements?\s+of.*equity': 'equity_statement',
            r'(?i)consolidated\s+statements?\s+of.*comprehensive': 'comprehensive_income',
            r'(?i)notes?\s+to.*consolidated.*financial\s+statements?': 'financial_notes',
            r'(?i)notes?\s+to.*financial\s+statements?': 'financial_notes',
            r'(?i)management.*discussion.*analysis': 'mda',
            r'(?i)table\s+of\s+contents': 'table_of_contents',
            r'(?i)signatures?\s*$': 'signatures'
        }
          # Check financial statement patterns
        for pattern, section_type in financial_patterns.items():
            if re.search(pattern, check_content):
                logger.debug(f"Detected financial section: {section_type}")
                return {"section_type": section_type}
        
        # If no specific pattern matches, return general
        return {"section_type": "general"}
    
    async def _generate_embeddings_for_chunks(self, chunks: List[DocumentChunk], 
                                             progress_callback=None):
        """
        Generate embeddings for document chunks with progress reporting
        """
        try:
            logger.info(f"Generating embeddings for {len(chunks)} chunks")
            
            for i, chunk in enumerate(chunks):
                try:
                    # Report progress for each embedding generation
                    if progress_callback:
                        percent = 70.0 + (i / len(chunks)) * 15.0  # 70-85% range
                        await progress_callback("processing", percent, f"Generating embedding {i+1}/{len(chunks)}")
                    
                    if self.azure_manager:
                        embedding = await self.azure_manager.get_embedding(chunk.content)
                        chunk.embedding = embedding
                    else:
                        # Skip embeddings if Azure manager not available
                        chunk.embedding = None
                        logger.debug(f"Skipped embedding for chunk {i+1}/{len(chunks)} (Azure not available)")
                    logger.debug(f"Processed chunk {i+1}/{len(chunks)}")
                    
                    # Add small delay for UI responsiveness in progress updates
                    if i % 5 == 0:  # Every 5 chunks, allow other tasks to run
                        await asyncio.sleep(0.01)
                        
                except Exception as e:
                    logger.warning(f"Failed to generate embedding for chunk {i}: {e}")
                    chunk.embedding = None
            
            if progress_callback:
                await progress_callback("processing", 85.0, f"Completed embeddings for {len(chunks)} chunks")
                    
        except Exception as e:
            logger.error(f"Error generating embeddings: {e}")
            if progress_callback:
                await progress_callback("processing", 85.0, f"Embedding generation failed: {str(e)[:50]}...")
            raise
    
    async def _prepare_search_documents(self, chunks: List[DocumentChunk]) -> List[Dict[str, Any]]:
        """
        Prepare documents for Azure Search indexing with proper schema mapping and credibility assessment
        """
        search_documents = []
        
        for chunk in chunks:
            if chunk.embedding is None:
                continue  # Skip chunks without embeddings
                
            # Extract metadata
            metadata = chunk.metadata
            
            # Assess credibility of the chunk using the credibility assessor
            try:
                if self.credibility_assessor:
                    # Create a processed document structure for credibility assessment
                    processed_doc = {
                        "extracted_content": {"content": chunk.content},
                        "metadata": metadata
                    }
                    source_url = metadata.get('source', 'SEC EDGAR')
                    credibility_score = await self.credibility_assessor.assess_credibility(
                        processed_doc, source_url
                    )
                    logger.debug(f"Assessed credibility score: {credibility_score:.3f} for chunk {chunk.chunk_id}")
                else:
                    # Default high credibility for SEC documents when assessor not available
                    credibility_score = 0.9
                    logger.debug(f"Using default credibility score: {credibility_score} for chunk {chunk.chunk_id}")
                
            except Exception as e:
                logger.warning(f"Failed to assess credibility for chunk {chunk.chunk_id}: {e}")
                credibility_score = 0.8  # Higher default for SEC documents
            
            # Use accession number as document_id for grouping
            document_id = metadata.get('accession_number', chunk.chunk_id.split('_')[0] if '_' in chunk.chunk_id else chunk.chunk_id)
            
            search_doc = {
                "id": chunk.chunk_id,  # Primary key
                "content": chunk.content,
                "title": f"{metadata.get('company_name', 'Unknown')} - {metadata.get('form_type', 'Unknown')}",
                "document_id": document_id,  # Document grouping identifier
                "source": metadata.get('source', 'SEC EDGAR'),
                "chunk_id": chunk.chunk_id,  # Also include as chunk_id field for filtering
                "document_type": metadata.get('document_type', 'SEC Filing'),
                "company": metadata.get('company_name', ''),
                "filing_date": metadata.get('filing_date', ''),
                "section_type": metadata.get('section_type', 'general'),
                "page_number": metadata.get('page_number', 0),
                "credibility_score": credibility_score,  # Use assessed credibility score
                "processed_at": datetime.now().isoformat(),
                "citation_info": json.dumps({
                    "ticker": metadata.get('ticker', ''),
                    "company_name": metadata.get('company_name', ''),
                    "form_type": metadata.get('form_type', ''),
                    "filing_date": metadata.get('filing_date', ''),
                    "accession_number": metadata.get('accession_number', ''),
                    "chunk_index": metadata.get('chunk_index', 0)
                }),
                # SEC-specific fields from Edgar tools - ensure these are all populated
                "ticker": metadata.get('ticker', ''),
                "cik": metadata.get('cik', ''),
                "industry": metadata.get('industry', ''),
                "sic": metadata.get('sic', ''),
                "entity_type": metadata.get('entity_type', ''),
                "form_type": metadata.get('form_type', ''),
                "accession_number": metadata.get('accession_number', ''),
                "period_end_date": metadata.get('period_end_date', ''),
                "chunk_index": metadata.get('chunk_index', 0),
                "content_type": metadata.get('content_type', 'text'),
                "chunk_method": metadata.get('chunk_method', 'unknown'),
                "file_size": metadata.get('file_size', 0) if metadata.get('file_size') is not None else 0,
                "document_url": metadata.get('document_url', ''),                "content_vector": chunk.embedding
            }
            search_documents.append(search_doc)
        
        return search_documents
    
    async def get_specific_filings(
        self, 
        ticker: str, 
        form_types: List[str] = None, 
        years: List[int] = None,
        limit: int = 50
    ) -> List[SECDocumentInfo]:
        """
        Get specific filings filtered by form types and years with improved company name handling
        """
        try:
            logger.info(f"Getting specific filings for {ticker}, forms: {form_types}, years: {years}")
            
            # First try to find the company (handles name-to-ticker mapping)
            companies = await self.search_companies(ticker)
            if not companies:
                logger.warning(f"No company found for query: {ticker}")
                return []
            
            # Use the first company's ticker
            actual_ticker = companies[0]['ticker']
            logger.info(f"Using ticker: {actual_ticker} for query: {ticker}")
            
            if form_types is None:
                form_types = ['10-K', '10-Q', '8-K']
            
            company = Company(actual_ticker)
            
            # Get more filings if we need to filter by years
            fetch_limit = limit * 3 if years else limit
            filings = company.get_filings(form=form_types).head(fetch_limit)
            
            documents = []
            for filing in filings:
                # Filter by years if specified
                if years and filing.filing_date.year not in years:
                    continue
                    
                doc_info = SECDocumentInfo(
                    ticker=actual_ticker,
                    company_name=company.name,
                    cik=str(company.cik),
                    form_type=filing.form,
                    filing_date=filing.filing_date,
                    period_end_date=getattr(filing, 'period_end_date', None),
                    document_url=getattr(filing, 'document_url', ''),
                    accession_number=filing.accession_number,
                    file_size=getattr(filing, 'size', None)
                )
                documents.append(doc_info)
                  # Stop if we have enough results
                if len(documents) >= limit:
                    break
            
            logger.info(f"Found {len(documents)} filings for {actual_ticker}")
            return documents
            
        except Exception as e:
            logger.error(f"Error getting specific filings for {ticker}: {e}")
            return []
