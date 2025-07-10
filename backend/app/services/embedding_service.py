import asyncio
import logging
from typing import List, Dict, Any, Optional
from openai import AsyncAzureOpenAI
from ..core.config import settings
import numpy as np

logger = logging.getLogger(__name__)

class EmbeddingService:
    """
    Service for generating vector embeddings using Azure OpenAI
    """
    
    def __init__(self):
        self.client = AsyncAzureOpenAI(
            api_key=settings.openai_key,
            api_version="2024-02-01",
            azure_endpoint=settings.openai_endpoint
        )
        self.embedding_model = settings.openai_embed_deployment or "text-embedding-3-small"
        self.batch_size = 100  # Process embeddings in batches
        self.max_retries = 3
        
    async def generate_embeddings_for_chunks(self, chunks: List[Dict[str, Any]], status_callback=None) -> List[Dict[str, Any]]:
        """
        Generate embeddings for a list of document chunks
        
        Args:
            chunks: List of chunk dictionaries with content
            status_callback: Optional callback for progress updates
            
        Returns:
            List of chunks with embeddings added
        """
        try:
            logger.info(f"Starting embedding generation for {len(chunks)} chunks")
            
            if status_callback:
                status_callback({
                    "step": "EMBEDDINGS",
                    "message": f"Generating embeddings for {len(chunks)} chunks",
                    "progress": 0
                })
            
            # Process chunks in batches
            enhanced_chunks = []
            total_processed = 0
            
            for i in range(0, len(chunks), self.batch_size):
                batch = chunks[i:i + self.batch_size]
                batch_num = i // self.batch_size + 1
                total_batches = (len(chunks) + self.batch_size - 1) // self.batch_size
                
                logger.info(f"Processing embedding batch {batch_num}/{total_batches}")
                
                # Generate embeddings for this batch
                batch_embeddings = await self._generate_batch_embeddings(batch)
                
                # Add embeddings to chunks
                for chunk, embedding in zip(batch, batch_embeddings):
                    if embedding is not None:
                        chunk_with_embedding = chunk.copy()
                        chunk_with_embedding['content_vector'] = embedding
                        chunk_with_embedding['embedding_model'] = self.embedding_model
                        chunk_with_embedding['embedding_dimensions'] = len(embedding)
                        enhanced_chunks.append(chunk_with_embedding)
                    else:
                        # Keep chunk without embedding if generation failed
                        logger.warning(f"Failed to generate embedding for chunk {chunk.get('id', 'unknown')}")
                        enhanced_chunks.append(chunk)
                
                total_processed += len(batch)
                progress = int((total_processed / len(chunks)) * 100)
                
                if status_callback:
                    status_callback({
                        "step": "EMBEDDINGS",
                        "message": f"Generated embeddings for {total_processed}/{len(chunks)} chunks",
                        "progress": progress
                    })
                
                # Rate limiting
                await asyncio.sleep(0.1)
            
            successful_embeddings = sum(1 for chunk in enhanced_chunks if 'content_vector' in chunk)
            logger.info(f"Successfully generated {successful_embeddings}/{len(chunks)} embeddings")
            
            return enhanced_chunks
            
        except Exception as e:
            logger.error(f"Error generating embeddings: {str(e)}")
            if status_callback:
                status_callback({
                    "step": "EMBEDDINGS",
                    "message": f"Embedding generation failed: {str(e)}",
                    "progress": 0
                })
            # Return chunks without embeddings
            return chunks
    
    async def _generate_batch_embeddings(self, chunks: List[Dict[str, Any]]) -> List[Optional[List[float]]]:
        """
        Generate embeddings for a batch of chunks
        """
        texts = []
        for chunk in chunks:
            content = chunk.get('content', '')
            # Limit content length for embedding (model limits)
            max_tokens = 8000  # Conservative limit for text-embedding-3-small
            if len(content) > max_tokens:
                content = content[:max_tokens]
            texts.append(content)
        
        embeddings = []
        
        for attempt in range(self.max_retries):
            try:
                # Generate embeddings using Azure OpenAI
                response = await self.client.embeddings.create(
                    input=texts,
                    model=self.embedding_model
                )
                
                # Extract embeddings from response
                for embedding_data in response.data:
                    embeddings.append(embedding_data.embedding)
                
                return embeddings
                
            except Exception as e:
                logger.warning(f"Embedding generation attempt {attempt + 1} failed: {str(e)}")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff
                else:
                    logger.error(f"All embedding generation attempts failed for batch")
                    # Return None for each chunk in the batch
                    return [None] * len(chunks)
        
        return [None] * len(chunks)
    
    async def generate_single_embedding(self, text: str) -> Optional[List[float]]:
        """
        Generate embedding for a single text
        """
        try:
            # Limit text length
            max_tokens = 8000
            if len(text) > max_tokens:
                text = text[:max_tokens]
            
            response = await self.client.embeddings.create(
                input=[text],
                model=self.embedding_model
            )
            
            return response.data[0].embedding
            
        except Exception as e:
            logger.error(f"Error generating single embedding: {str(e)}")
            return None
    
    def calculate_similarity(self, embedding1: List[float], embedding2: List[float]) -> float:
        """
        Calculate cosine similarity between two embeddings
        """
        try:
            # Convert to numpy arrays
            vec1 = np.array(embedding1)
            vec2 = np.array(embedding2)
            
            # Calculate cosine similarity
            dot_product = np.dot(vec1, vec2)
            norm1 = np.linalg.norm(vec1)
            norm2 = np.linalg.norm(vec2)
            
            if norm1 == 0 or norm2 == 0:
                return 0.0
            
            similarity = dot_product / (norm1 * norm2)
            return float(similarity)
            
        except Exception as e:
            logger.error(f"Error calculating similarity: {str(e)}")
            return 0.0
    
    async def find_similar_chunks(self, query_text: str, chunks: List[Dict[str, Any]], top_k: int = 5) -> List[Dict[str, Any]]:
        """
        Find most similar chunks to a query text
        """
        try:
            # Generate embedding for query
            query_embedding = await self.generate_single_embedding(query_text)
            if query_embedding is None:
                return []
            
            # Calculate similarities
            similarities = []
            for chunk in chunks:
                if 'content_vector' in chunk:
                    similarity = self.calculate_similarity(query_embedding, chunk['content_vector'])
                    similarities.append((chunk, similarity))
            
            # Sort by similarity and return top k
            similarities.sort(key=lambda x: x[1], reverse=True)
            return [chunk for chunk, _ in similarities[:top_k]]
            
        except Exception as e:
            logger.error(f"Error finding similar chunks: {str(e)}")
            return [] 