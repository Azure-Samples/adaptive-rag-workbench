#!/usr/bin/env python3
"""
Full test of LLM-synthesized answer to see the complete output.
"""

import asyncio
import logging
import os
import sys

# Add the backend directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def test_full_answer():
    """Test full LLM-synthesized answer output."""
    
    logger.info("Testing full LLM-synthesized answer...")
    logger.info("=" * 60)
    
    # Import and initialize the service
    from app.services.agentic_vector_rag_service import agentic_rag_service
    
    # Test question
    question = "How did Microsoft's revenue perform in their latest financial results?"
    
    try:
        # Process the question using agentic RAG
        result = await agentic_rag_service.process_question(
            question=question,
            conversation_history=[],
            rag_mode="agentic-rag"
        )
        
        logger.info("✅ AGENTIC RAG PROCESSING COMPLETED")
        logger.info("=" * 60)
        
        # Get the full answer
        answer = result.get("answer", "No answer generated")
        
        # Print the full answer
        logger.info("📄 FULL LLM-SYNTHESIZED ANSWER:")
        logger.info("=" * 60)
        print(answer)
        logger.info("=" * 60)
        
        # Check length
        logger.info(f"✅ Answer length: {len(answer)} characters")
        
        # Check structure
        has_headings = "#" in answer
        has_sections = "##" in answer
        has_analysis = "analysis" in answer.lower()
        
        logger.info(f"✅ Has headings: {has_headings}")
        logger.info(f"✅ Has sections: {has_sections}")
        logger.info(f"✅ Contains analysis: {has_analysis}")
        
        logger.info("=" * 60)
        logger.info("✅ FULL ANSWER TEST COMPLETED")
        
    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(test_full_answer())
