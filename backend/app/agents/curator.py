from typing import AsyncIterator
import asyncio
from pathlib import Path
from ..ingestion.di_extract import extract_pdf_content
from ..ingestion.indexer_job import upsert_chunks
import hashlib

class CuratorAgent:
    def __init__(self, kernel):
        self.kernel = kernel
        self.watch_dir = Path("data/ingest_drop")
        self.watch_dir.mkdir(parents=True, exist_ok=True)
    
    async def invoke_stream(self, file_path: str) -> AsyncIterator[str]:
        try:
            yield "Starting document processing...\n"
            await asyncio.sleep(0.5)
            
            pdf_path = Path(file_path)
            if not pdf_path.exists():
                yield f"Error: File {file_path} not found\n"
                return
            
            yield "Extracting content with Document Intelligence...\n"
            doc_result = await extract_pdf_content(pdf_path)
            
            if "Error" in doc_result.get("content", ""):
                yield f"Error extracting content: {doc_result['content']}\n"
                return
            
            yield "Chunking document content...\n"
            chunks = self._create_chunks(doc_result, pdf_path.stem)
            
            yield f"Generated {len(chunks)} chunks. Indexing...\n"
            await upsert_chunks(chunks)
            
            yield f"Successfully indexed {len(chunks)} chunks from {pdf_path.name}\n"
            yield "Document processing completed. Knowledge base updated.\n"
            
        except Exception as e:
            yield f"Error processing document: {str(e)}\n"
    
    def _create_chunks(self, doc_result: dict, filename: str) -> list:
        content = doc_result.get("content", "")
        if not content:
            return []
        
        paragraphs = content.split('\n\n')
        chunks = []
        
        for i, paragraph in enumerate(paragraphs):
            if len(paragraph.strip()) > 100:
                chunk_id = hashlib.md5(f"{filename}_{i}_{paragraph[:50]}".encode()).hexdigest()
                chunks.append({
                    "id": chunk_id,
                    "content": paragraph.strip(),
                    "source": f"{filename}.pdf",
                    "company": self._extract_company(filename),
                    "year": self._extract_year(filename)
                })
        
        return chunks
    
    def _extract_company(self, filename: str) -> str:
        filename_lower = filename.lower()
        if "apple" in filename_lower:
            return "Apple"
        elif "microsoft" in filename_lower:
            return "Microsoft"
        elif "google" in filename_lower or "alphabet" in filename_lower:
            return "Google"
        elif "meta" in filename_lower:
            return "Meta"
        elif "jpmc" in filename_lower or "jpmorgan" in filename_lower:
            return "JPMC"
        elif "microsoft" in filename_lower:
            return "Microsoft"
        else:
            return "Unknown"
    
    def _extract_year(self, filename: str) -> str:
        import re
        year_match = re.search(r'20\d{2}', filename)
        return str(year_match.group()) if year_match else "2024"
