"""
Custom chunker implementation based on md2chunks
Provides intelligent text chunking for SEC documents and other financial content
"""

import re
import logging
from typing import List, Tuple, Dict, Any, Optional
import tiktoken

from app.core.config import settings

logger = logging.getLogger(__name__)

# Configuration constants - use settings where available
CHUNK_SIZE = getattr(settings, 'chunk_size', 1500)
CHUNK_OVERLAP = getattr(settings, 'chunk_overlap', 200)
CHUNK_OVERLAP_BUFFER = 1.4  # Buffer defines the upper limit and has to be above 1
CHARACTER_SEPARATOR = ["\n\n", "\n", ".", " "]
PARAGRAPH_SEPARATOR = "\n\n\n"
BREAK_SEPARATOR = "\n---\n"
DEFAULT_TOKENIZER = "gpt-3.5-turbo"

# Common abbreviations to handle specially
ABBREVIATIONS = [
    "eg.", "i.e.", "vs.", "Dr.", "Mr.", "Ms.", "Inc.", "Corp.", "Ltd.", 
    "LLC.", "CEO.", "CFO.", "COO.", "CTO.", "VP.", "SVP.", "EVP.",
    "Q1.", "Q2.", "Q3.", "Q4.", "FY.", "YTD.", "EBITDA.", "SEC.", "NYSE.", "NASDAQ."
]


class DocumentChunker:
    """
    Advanced text chunker with special handling for financial documents
    """
    
    def __init__(
        self,
        chunk_size: int = CHUNK_SIZE,
        paragraph_separator: List[str] = None,
        character_separator: List[str] = None,
        tokenizer: str = DEFAULT_TOKENIZER,
    ):
        """
        Initialize the chunker with specified parameters
        
        Args:
            chunk_size: Maximum size of each chunk in tokens
            paragraph_separator: List of paragraph separators
            character_separator: List of character separators
            tokenizer: Tokenizer model to use
        """
        self.chunk_size = chunk_size
        self.paragraph_separator = paragraph_separator or [PARAGRAPH_SEPARATOR]
        self.character_separator = character_separator or CHARACTER_SEPARATOR
        
        # Initialize tokenizer
        try:
            self.tokenizer = tiktoken.encoding_for_model(tokenizer)
        except Exception as e:
            logger.warning(f"Tokenizer {tokenizer} not supported, falling back to cl100k_base: {e}")
            self.tokenizer = tiktoken.get_encoding("cl100k_base")
    
    def token_count(self, text: str) -> int:
        """Return the token count of the given text"""
        if not text:
            return 0
        try:
            return len(self.tokenizer.encode(text))
        except Exception:
            # Fallback to character count approximation
            return len(text) // 4
    
    def chunk(
        self, 
        content: str, 
        chunk_size: int = None, 
        overlap: int = CHUNK_OVERLAP,  # Use configured overlap
        separator: str = "\n\n",
        metadata: Dict[str, Any] = None
    ) -> List[Dict[str, Any]]:
        """
        Main chunking method that returns structured chunk data
        
        Args:
            content: Text content to chunk
            chunk_size: Override default chunk size
            overlap: Overlap between chunks (not used in current implementation)
            separator: Preferred separator (not used in current implementation)
            metadata: Additional metadata to include
            
        Returns:
            List of chunk dictionaries with content and metadata
        """
        if chunk_size:
            self.chunk_size = chunk_size
            
        chunks = self.split_text(content, metadata_str="", is_md=True)
        
        result = []
        for i, chunk_content in enumerate(chunks):
            chunk_data = {
                "content": chunk_content,
                "metadata": {
                    "chunk_index": i,
                    "token_count": self.token_count(chunk_content),
                    "chunking_method": "md2chunks_adapted",
                    **(metadata or {})
                }
            }
            result.append(chunk_data)
        
        return result
    
    def _abbreviation_handler(self, text: str, alter: bool) -> str:
        """Handle abbreviations by replacing periods with special markers"""
        if alter:
            for abbr in ABBREVIATIONS:
                pattern = rf"\b{re.escape(abbr)}(?=\s|$)"
                replacement = abbr.replace(".", "*-*")
                text = re.sub(pattern, replacement, text)
        else:
            text = text.replace("*-*", ".")
        return text
    
    def _url_handler(self, text: str, alter: bool) -> str:
        """Handle URLs by replacing periods with special markers"""
        if alter:
            text = re.sub(
                r"[-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b([-a-zA-Z0-9()@:%_\+.~#?&//=]*)",
                lambda match: match.group().replace(".", "@-@"),
                text,
            )
        else:
            text = text.replace("@-@", ".")
        return text
    
    def _decimal_handler(self, text: str, alter: bool) -> str:
        """Handle decimals by replacing periods with special markers"""
        if alter:
            text = re.sub(r"(?<=\d)\.(?=\d)", "#-#", text)
        else:
            text = text.replace("#-#", ".")
        return text
    
    def special_case_handler(self, text: str, alter: bool) -> str:
        """Apply all special case handlers"""
        handlers = [
            self._decimal_handler,
            self._url_handler,
            self._abbreviation_handler,
        ]
        
        for handler in handlers:
            text = handler(text, alter)
        return text
    
    def _merge(
        self, 
        splits: List[Tuple[str, str]], 
        chunk_size_limit: int
    ) -> List[Tuple[str, str]]:
        """Merge split texts into chunks without exceeding chunk size"""
        merged = False
        for idx, (context, chunk) in enumerate(splits):
            if idx == 0:
                continue
            
            prev_chunk_context = splits[idx - 1][0]
            prev_chunk = splits[idx - 1][1]
            prev_chunk_size = self.token_count(prev_chunk_context + prev_chunk)
            
            # If header context is different, include context in chunk
            if prev_chunk_context != context:
                token_count = self.token_count(context + chunk)
                chunk = context + chunk
            else:
                token_count = self.token_count(chunk)
            
            # Merge if combined size is within buffer
            if prev_chunk_size + token_count < int(chunk_size_limit * CHUNK_OVERLAP_BUFFER):
                splits[idx - 1] = (prev_chunk_context, prev_chunk + chunk)
                splits.pop(idx)
                merged = True
        
        # Recursively merge until no more merging possible
        if merged:
            splits = self._merge(splits, chunk_size_limit)
        
        return splits
    
    def _character_splits(
        self, 
        context: str, 
        content: str, 
        chunk_size_limit: int, 
        is_md: bool
    ) -> List[Tuple[str, str]]:
        """Split text by characters when other methods fail"""
        chunks: List[Tuple[str, str]] = [(context, content)]
        
        for separator in self.character_separator:
            is_split_more = False
            char_splits = []
            
            for context, chunk in chunks:
                token_size = self.token_count(context + chunk)
                
                if token_size > chunk_size_limit * CHUNK_OVERLAP_BUFFER:
                    chunk_splits = []
                    splits = chunk.split(separator)
                    len_splits = len(splits)
                    
                    for i, split in enumerate(splits):
                        if i != len_splits - 1:
                            chunk_splits.append(context + split + separator)
                        else:
                            chunk_splits.append(context + split)
                    
                    char_splits.extend(chunk_splits)
                    is_split_more = True
                else:
                    char_splits.append(context + chunk)
            
            # Process markdown chunks for header context
            if is_md:
                processed_splits = self._md_chunk_treatment(chunks=char_splits)
            else:
                processed_splits = [("", split) for split in char_splits]
            
            if is_split_more:
                chunks = self._merge(processed_splits, chunk_size_limit)
            else:
                return processed_splits
        
        return chunks
    
    def _md_chunk_treatment(self, chunks: List[str]) -> List[Tuple[str, str]]:
        """Treat markdown chunks by maintaining header context"""
        context = ""
        new_chunks: List[Tuple[str, str]] = []
        
        for chunk in chunks:
            # Find markdown headers
            matches = re.findall(r"(?s)#\s.+?\n\n(?!#)", chunk)
            
            if not matches:
                new_chunks.append((context, chunk))
            else:
                if re.match("^#.+?\n", chunk):
                    chunk = re.sub(r"(?s)^#\s.+?\n\n(?!#)", "", chunk)
                    new_chunks.append((matches[0], chunk))
                else:
                    new_chunks.append((context, chunk))
                context = matches[-1]
        
        return new_chunks
    
    def _paragraph_splits(
        self, 
        content: str, 
        is_md: bool
    ) -> List[Tuple[str, str, int]]:
        """Split text by paragraphs and calculate token counts"""
        chunks: List[Tuple[str, str, int]] = []
        para_splits = content.split(PARAGRAPH_SEPARATOR)
        
        if is_md:
            para_splits = [
                (
                    split.strip("\n") + PARAGRAPH_SEPARATOR
                    if i != len(para_splits) - 1
                    else split
                )
                for i, split in enumerate(para_splits)
            ]
            splits = self._md_chunk_treatment(chunks=para_splits)
        else:
            splits = [("", split.strip("\n")) for split in para_splits]
        
        for context, split in splits:
            token_count = self.token_count(context + split)
            chunks.append((context, split, token_count))
        
        return chunks
    
    def split_text(self, content: str, metadata_str: str, is_md: bool) -> List[str]:
        """
        Split input text into chunks based on configured chunk size
        
        Args:
            content: Content to split
            metadata_str: Metadata string to consider in chunk size calculation
            is_md: Whether content is in markdown format
            
        Returns:
            List of text chunks
        """
        if not content:
            return []
        
        # Calculate effective chunk size considering metadata
        if metadata_str:
            num_extra_tokens = self.token_count(metadata_str)
            chunk_size_limit = self.chunk_size - num_extra_tokens
            if chunk_size_limit <= 0:
                raise ValueError(
                    "Effective chunk size is non-positive after considering metadata"
                )
        else:
            chunk_size_limit = self.chunk_size
        
        token_size = self.token_count(content)
        
        # If content fits in one chunk, return as is
        if token_size < chunk_size_limit:
            return [content]
        
        # Apply special case handling
        content = self.special_case_handler(content, alter=True)
        
        # Split by break separators first
        big_splits = content.split(BREAK_SEPARATOR)
        chunks = []
        
        for split in big_splits:
            chunks.extend(self._paragraph_splits(split.strip("\n"), is_md))
        
        all_chunks: List[Tuple[str, str]] = []
        
        for context, split, token_size in chunks:
            if token_size > chunk_size_limit * CHUNK_OVERLAP_BUFFER:
                chunk_split = self._character_splits(
                    context, split, chunk_size_limit, is_md
                )
                all_chunks.extend(chunk_split)
            else:
                all_chunks.append((context, split))
        
        # Final merge pass
        all_chunks = self._merge(all_chunks, chunk_size_limit)
        
        # Prepare final chunks
        final_chunks = []
        for context, chunk in all_chunks:
            chunk = chunk.strip()
            # Replace pipes with semicolons for table compatibility
            context = context.replace("|", ";")
            chunk = chunk.replace("|", ";")
            
            if chunk:
                chunk = self.special_case_handler(chunk, alter=False)
                final_chunks.append(context + chunk)
        
        return final_chunks
