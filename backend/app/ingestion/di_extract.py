from pathlib import Path
from typing import Dict, Any, List
import logging
from ..services.azure_services import get_azure_service_manager

logger = logging.getLogger(__name__)

async def extract_pdf_content(file_path: Path) -> Dict[str, Any]:
    """
    Extract content from PDF using Azure Document Intelligence via centralized service manager
    with enhanced metadata extraction and structure preservation
    """
    try:
        logger.info(f"Starting Document Intelligence extraction for {file_path.name}")
        
        # Use the centralized Azure Service Manager which handles both real and mock services
        azure_service = await get_azure_service_manager()
        
        with open(file_path, "rb") as f:
            file_bytes = f.read()
        
        logger.info(f"File size: {len(file_bytes)} bytes")
        
        if len(file_bytes) == 0:
            raise Exception("File is empty")
        
        # Use the Azure Service Manager to analyze the document
        try:
            logger.info("Starting Document Intelligence analysis via Azure Service Manager...")
            result = await azure_service.analyze_document(
                document_content=file_bytes,
                content_type="application/pdf",
                filename=file_path.name
            )
            logger.info("Document Intelligence analysis completed successfully")
        except Exception as di_error:
            logger.error(f"Document Intelligence analysis failed: {str(di_error)}")
            raise Exception(f"Document Intelligence service error: {str(di_error)}")
        
        # Validate the result
        if not result or not result.get('content'):
            raise Exception("Document Intelligence returned empty result")
        
        # The Azure Service Manager already returns structured data, but we need to adapt it
        # to the format expected by the enhanced processor
        try:
            extracted_data = _adapt_azure_service_result(result, file_path.name)
        except Exception as extract_error:
            logger.error(f"Error adapting DI result: {extract_error}")
            # Return basic structure with available content
            return {
                "content": result.get('content', ''),
                "pages": [],
                "tables": result.get('tables', []),
                "paragraphs": [],
                "key_value_pairs": result.get('key_value_pairs', {}),
                "document_metadata": {"content_length": len(result.get('content', ''))},
                "structure_info": {}
            }
        
        logger.info(f"Extracted {len(extracted_data.get('pages', []))} pages, "
                   f"{len(extracted_data.get('tables', []))} tables, "
                   f"{len(extracted_data.get('paragraphs', []))} paragraphs")
        
        return extracted_data
        
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Error extracting content from {file_path.name}: {error_msg}")
        
        # Don't return error content, raise exception so fallback can handle it
        raise Exception(f"Document Intelligence extraction failed: {error_msg}")

def _adapt_azure_service_result(result: Dict[str, Any], filename: str) -> Dict[str, Any]:
    """
    Adapt the Azure Service Manager result to the expected format
    """
    try:
        logger.info(f"[{filename}] Adapting Azure service result, keys: {list(result.keys())}")
        logger.info(f"[{filename}] Raw content length: {len(result.get('content', ''))}")
        logger.info(f"[{filename}] Raw content preview: {repr(result.get('content', '')[:200])}")
        
        extracted = {
            "content": result.get('content', ''),
            "pages": [],
            "tables": result.get('tables', []),
            "paragraphs": [],
            "key_value_pairs": [],
            "document_metadata": {},
            "structure_info": {}
        }
        
        # Create basic page structure if not available
        content_length = len(extracted["content"])
        if content_length > 0:
            # Estimate pages based on content length (rough approximation)
            estimated_pages = max(1, content_length // 3000)  # ~3000 chars per page
            for i in range(estimated_pages):
                page_data = {
                    "page_number": i + 1,
                    "width": 612,  # Standard letter size
                    "height": 792,
                    "unit": "pixel",
                    "text_angle": 0,
                    "lines": [],
                    "words": []
                }
                extracted["pages"].append(page_data)
        
        # Convert key_value_pairs from dict to list format
        kv_pairs = result.get('key_value_pairs', {})
        if isinstance(kv_pairs, dict):
            for key, value_data in kv_pairs.items():
                kv_data = {
                    "key": key,
                    "value": value_data.get('value', '') if isinstance(value_data, dict) else str(value_data),
                    "confidence": value_data.get('confidence', 0.0) if isinstance(value_data, dict) else 0.0
                }
                extracted["key_value_pairs"].append(kv_data)
        
        # Create document metadata
        extracted["document_metadata"] = {
            "page_count": len(extracted["pages"]),
            "table_count": len(extracted["tables"]),
            "paragraph_count": 0,  # Will be estimated below
            "has_tables": len(extracted["tables"]) > 0,
            "has_key_value_pairs": len(extracted["key_value_pairs"]) > 0,
            "content_length": content_length
        }
        
        # Create basic paragraph structure from content
        content = extracted["content"]
        if content:
            paragraphs = content.split('\n\n')  # Split on double newlines
            for i, para_text in enumerate(paragraphs):
                if para_text.strip():
                    para_data = {
                        "content": para_text.strip(),
                        "role": "paragraph",
                        "bounding_regions": [],
                        "paragraph_id": i
                    }
                    extracted["paragraphs"].append(para_data)
            
            extracted["document_metadata"]["paragraph_count"] = len(extracted["paragraphs"])
        
        # Structure analysis for credibility assessment
        extracted["structure_info"] = _analyze_document_structure(extracted)
        
        return extracted
        
    except Exception as e:
        logger.error(f"Error adapting Azure service result: {str(e)}")
        # Return minimal structure
        return {
            "content": result.get('content', ''),
            "pages": [{"page_number": 1, "width": 612, "height": 792, "unit": "pixel", "text_angle": 0, "lines": [], "words": []}],
            "tables": [],
            "paragraphs": [],
            "key_value_pairs": [],
            "document_metadata": {"content_length": len(result.get('content', ''))},
            "structure_info": {}
        }

def _extract_comprehensive_data(result) -> Dict[str, Any]:
    """
    Extract comprehensive data from Document Intelligence AnalyzeResult
    """
    try:
        extracted = {
            "content": "",
            "pages": [],
            "tables": [],
            "paragraphs": [],
            "key_value_pairs": [],
            "document_metadata": {},
            "structure_info": {}
        }
        
        # Extract main content
        if hasattr(result, 'content') and result.content:
            extracted["content"] = result.content
            logger.info(f"Extracted content length: {len(extracted['content'])} characters")
        
        # Extract pages with detailed information
        if hasattr(result, 'pages') and result.pages:
            for page_idx, page in enumerate(result.pages):
                page_data = {
                    "page_number": page_idx + 1,
                    "width": getattr(page, 'width', 0),
                    "height": getattr(page, 'height', 0),
                    "unit": getattr(page, 'unit', 'pixel'),
                    "text_angle": getattr(page, 'angle', 0),
                    "lines": [],
                    "words": []
                }
                
                # Extract lines
                if hasattr(page, 'lines') and page.lines:
                    for line in page.lines:
                        line_data = {
                            "content": getattr(line, 'content', ''),
                            "bounding_polygon": _extract_polygon(line),
                        }
                        page_data["lines"].append(line_data)
                
                # Extract words for detailed positioning
                if hasattr(page, 'words') and page.words:
                    for word in page.words:
                        word_data = {
                            "content": getattr(word, 'content', ''),
                            "confidence": getattr(word, 'confidence', 0),
                            "bounding_polygon": _extract_polygon(word),
                        }
                        page_data["words"].append(word_data)
                
                extracted["pages"].append(page_data)
        
        # Extract tables with structure
        if hasattr(result, 'tables') and result.tables:
            for table_idx, table in enumerate(result.tables):
                table_data = {
                    "table_id": table_idx,
                    "row_count": getattr(table, 'row_count', 0),
                    "column_count": getattr(table, 'column_count', 0),
                    "bounding_regions": _extract_bounding_regions(table),
                    "cells": []
                }
                
                if hasattr(table, 'cells') and table.cells:
                    for cell in table.cells:
                        cell_data = {
                            "content": getattr(cell, 'content', ''),
                            "row_index": getattr(cell, 'row_index', 0),
                            "column_index": getattr(cell, 'column_index', 0),
                            "row_span": getattr(cell, 'row_span', 1),
                            "column_span": getattr(cell, 'column_span', 1),
                            "kind": getattr(cell, 'kind', 'content'),
                            "bounding_regions": _extract_bounding_regions(cell)
                        }
                        table_data["cells"].append(cell_data)
                
                extracted["tables"].append(table_data)
        
        # Extract paragraphs for intelligent chunking
        if hasattr(result, 'paragraphs') and result.paragraphs:
            for para_idx, paragraph in enumerate(result.paragraphs):
                para_data = {
                    "content": getattr(paragraph, 'content', ''),
                    "role": getattr(paragraph, 'role', 'paragraph'),
                    "bounding_regions": _extract_bounding_regions(paragraph),
                    "paragraph_id": para_idx
                }
                extracted["paragraphs"].append(para_data)
        
        # Extract key-value pairs if available
        if hasattr(result, 'key_value_pairs') and result.key_value_pairs:
            for kv_pair in result.key_value_pairs:
                kv_data = {
                    "key": getattr(kv_pair.key, 'content', '') if hasattr(kv_pair, 'key') and kv_pair.key else '',
                    "value": getattr(kv_pair.value, 'content', '') if hasattr(kv_pair, 'value') and kv_pair.value else '',
                    "confidence": getattr(kv_pair, 'confidence', 0)
                }
                extracted["key_value_pairs"].append(kv_data)
        
        # Extract document-level metadata
        extracted["document_metadata"] = {
            "page_count": len(extracted["pages"]),
            "table_count": len(extracted["tables"]),
            "paragraph_count": len(extracted["paragraphs"]),
            "has_tables": len(extracted["tables"]) > 0,
            "has_key_value_pairs": len(extracted["key_value_pairs"]) > 0,
            "content_length": len(extracted["content"])
        }
        
        # Structure analysis for credibility assessment
        extracted["structure_info"] = _analyze_document_structure(extracted)
        
        return extracted
        
    except Exception as e:
        logger.error(f"Error extracting comprehensive data: {str(e)}")
        return {"content": f"Error processing document structure: {str(e)}"}

def _extract_polygon(element) -> List[Dict[str, float]]:
    """Extract bounding polygon coordinates from element"""
    try:
        if hasattr(element, 'polygon') and element.polygon:
            return [{"x": point.x, "y": point.y} for point in element.polygon]
        elif hasattr(element, 'bounding_box') and element.bounding_box:
            # Convert bounding box to polygon format
            bb = element.bounding_box
            return [
                {"x": bb.x, "y": bb.y},
                {"x": bb.x + bb.width, "y": bb.y},
                {"x": bb.x + bb.width, "y": bb.y + bb.height},
                {"x": bb.x, "y": bb.y + bb.height}
            ]
        return []
    except Exception:
        return []

def _extract_bounding_regions(element) -> List[Dict[str, Any]]:
    """Extract bounding regions from element"""
    try:
        regions = []
        if hasattr(element, 'bounding_regions') and element.bounding_regions:
            for region in element.bounding_regions:
                region_data = {
                    "page_number": getattr(region, 'page_number', 1),
                    "polygon": _extract_polygon(region) if hasattr(region, 'polygon') else []
                }
                regions.append(region_data)
        return regions
    except Exception:
        return []

def _analyze_document_structure(extracted_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Analyze document structure for credibility assessment and intelligent processing
    """
    try:
        structure = {
            "document_type": "financial_filing",
            "has_formal_structure": False,
            "section_headers": [],
            "credibility_indicators": {
                "has_tables": len(extracted_data.get("tables", [])) > 0,
                "has_structured_content": len(extracted_data.get("paragraphs", [])) > 5,
                "content_density": 0,
                "professional_formatting": False
            },
            "processing_recommendations": []
        }
        
        content = extracted_data.get("content", "")
        if content:
            # Analyze content density
            structure["credibility_indicators"]["content_density"] = len(content.split()) / max(len(content), 1)
            
            # Check for section headers (common in financial documents)
            common_headers = [
                "BUSINESS", "RISK FACTORS", "MANAGEMENT", "FINANCIAL", 
                "OPERATIONS", "LIQUIDITY", "CONTROLS", "LEGAL"
            ]
            
            for header in common_headers:
                if header in content.upper():
                    structure["section_headers"].append(header)
            
            structure["has_formal_structure"] = len(structure["section_headers"]) > 2
            structure["credibility_indicators"]["professional_formatting"] = structure["has_formal_structure"]
        
        # Processing recommendations based on structure
        if structure["has_formal_structure"]:
            structure["processing_recommendations"].append("Use section-aware chunking")
        
        if structure["credibility_indicators"]["has_tables"]:
            structure["processing_recommendations"].append("Extract and preserve table structure")
        
        if structure["credibility_indicators"]["content_density"] > 0.1:
            structure["processing_recommendations"].append("Use semantic chunking with overlap")
        
        return structure
        
    except Exception as e:
        logger.error(f"Error analyzing document structure: {str(e)}")
        return {"error": str(e)}

async def extract_html_content(file_path: Path) -> Dict[str, Any]:
    """
    Extract content from HTML files with structure preservation
    """
    try:
        logger.info(f"Extracting HTML content from {file_path.name}")
        
        with open(file_path, "r", encoding="utf-8") as f:
            html_content = f.read()
        
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Remove script and style elements
        for script in soup(["script", "style"]):
            script.decompose()
        
        # Extract structured content
        text = soup.get_text()
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        clean_text = ' '.join(chunk for chunk in chunks if chunk)
        
        # Extract tables if present
        tables = []
        for table in soup.find_all('table'):
            table_data = {
                "html": str(table),
                "text": table.get_text(strip=True, separator=' | ')
            }
            tables.append(table_data)
        
        # Extract headings for structure
        headings = []
        for heading in soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6']):
            headings.append({
                "level": heading.name,
                "text": heading.get_text(strip=True)
            })
        
        result = {
            "content": clean_text,
            "tables": tables,
            "headings": headings,
            "document_metadata": {
                "page_count": 1,
                "table_count": len(tables),
                "heading_count": len(headings),
                "content_length": len(clean_text)
            },
            "structure_info": {
                "document_type": "html_document",
                "has_formal_structure": len(headings) > 0,
                "credibility_indicators": {
                    "has_tables": len(tables) > 0,
                    "has_structured_content": len(headings) > 0,
                    "content_density": len(clean_text.split()) / max(len(clean_text), 1) if clean_text else 0
                }
            }
        }
        
        logger.info(f"HTML extraction completed: {len(clean_text)} chars, {len(tables)} tables, {len(headings)} headings")
        return result
        
    except Exception as e:
        logger.error(f"Error extracting HTML content from {file_path.name}: {str(e)}")
        return {"content": f"Error extracting content: {str(e)}"}
