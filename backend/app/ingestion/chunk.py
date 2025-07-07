import tiktoken
import hashlib
from typing import Iterator, Dict, List

def chunk_document(text: str, *, size: int = 1000, overlap: int = 20, company: str = "", year: str = "2024") -> Iterator[Dict]:
    enc = tiktoken.get_encoding("cl100k_base")
    tokens = enc.encode(text)
    
    for i in range(0, len(tokens), size - overlap):
        window = tokens[i : i + size]
        chunk_text = enc.decode(window)
        
        if len(chunk_text.strip()) < 50:
            continue
            
        chunk_id = hashlib.md5(f"{company}_{year}_{chunk_text}".encode()).hexdigest()
        
        yield {
            "id": chunk_id,
            "content": chunk_text.strip(),
            "source": f"{company}_{year}_10-K",
            "company": company,
            "year": year
        }

def chunk_content(content: str, source: str, company: str = "Unknown", year: str = "2024", size: int = 1000, overlap: int = 20) -> List[Dict]:
    """
    Chunk content into smaller pieces with proper schema for Azure Search indexing
    """
    enc = tiktoken.get_encoding("cl100k_base")
    tokens = enc.encode(content)
    chunks = []
    
    for i, window_start in enumerate(range(0, len(tokens), size - overlap)):
        window = tokens[window_start : window_start + size]
        chunk_text = enc.decode(window)
        
        if len(chunk_text.strip()) < 50:
            continue
            
        chunk_id = hashlib.md5(f"{source}_{i}_{chunk_text[:100]}".encode()).hexdigest()
        
        chunk = {
            "id": chunk_id,
            "content": chunk_text.strip(),
            "source": source,
            "company": company,
            "year": year,
            "content_length": len(chunk_text),
            "word_count": len(chunk_text.split()),
            "chunk_index": i
        }
        chunks.append(chunk)
    
    return chunks
