import asyncio
import logging
from app.services.agentic_vector_rag_service import agentic_rag_service

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_agentic_rag():
    """Test agentic RAG service functionality"""
    
    try:
        # Initialize the service
        await agentic_rag_service.initialize()
        
        # Test question
        question = "How did Microsoft perform in Q3 2024 earnings?"
        
        logger.info(f"Testing agentic RAG with question: {question}")
        
        # Process the question
        result = await agentic_rag_service.process_question(
            question=question,
            conversation_history=None,
            rag_mode="agentic-rag",
            session_id="test-session"
        )
        
        logger.info("Agentic RAG completed successfully!")
        logger.info(f"Answer length: {len(result.get('answer', ''))}")
        logger.info(f"Citations: {len(result.get('citations', []))}")
        logger.info(f"Query rewrites: {len(result.get('query_rewrites', []))}")
        logger.info(f"Activity steps: {len(result.get('activity_steps', []))}")
        logger.info(f"Retrieval method: {result.get('retrieval_method', 'unknown')}")
        logger.info(f"Success: {result.get('success', False)}")
        
        # Print first part of answer
        answer = result.get('answer', '')
        if answer:
            logger.info(f"Answer preview: {answer[:200]}...")
        
        # Print citation details
        citations = result.get('citations', [])
        if citations:
            logger.info(f"First citation: {citations[0]}")
        
        return result
        
    except Exception as e:
        logger.error(f"Test failed: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(test_agentic_rag())
