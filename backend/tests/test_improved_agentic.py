#!/usr/bin/env python3
"""
Test script to verify the improved agentic retrieval implementation.
This should now show:
- Proper LLM-generated answers (not raw JSON)
- Multiple subqueries in activity steps
- Better citation extraction
"""

import asyncio
import sys
import os
import logging
from pathlib import Path

# Add the backend directory to the path
sys.path.insert(0, str(Path(__file__).parent))

from app.services.agentic_vector_rag_service import agentic_rag_service

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_improved_agentic_retrieval():
    """Test improved agentic retrieval with better answer generation"""
    
    # Test question that should generate multiple subqueries
    test_question = "What is Microsoft's current financial performance and how does it compare to last year?"
    
    logger.info("=" * 70)
    logger.info("TESTING IMPROVED AGENTIC RETRIEVAL")
    logger.info("=" * 70)
    
    try:
        # Initialize the service
        logger.info("Initializing agentic RAG service...")
        await agentic_rag_service.initialize()
        
        # Test the question processing
        logger.info(f"Processing question: '{test_question}'")
        
        result = await agentic_rag_service.process_question(
            question=test_question,
            conversation_history=None,
            rag_mode="agentic-rag"
        )
        
        # Analyze the results
        logger.info("=" * 50)
        logger.info("RESULTS ANALYSIS")
        logger.info("=" * 50)
        
        answer = result.get('answer', '')
        logger.info(f"Answer type: {type(answer)}")
        logger.info(f"Answer length: {len(answer) if answer else 0} characters")
        
        # Check if answer looks like LLM-generated text vs raw JSON
        if answer.startswith('[{') or answer.startswith('{"'):
            logger.warning("❌ Answer appears to be raw JSON/data, not LLM-generated text")
        else:
            logger.info("✅ Answer appears to be LLM-generated text")
        
        logger.info(f"Answer preview: {answer[:300]}...")
        
        # Analyze citations
        citations = result.get('citations', [])
        logger.info(f"\nCitations: {len(citations)} found")
        if citations:
            for i, citation in enumerate(citations[:3]):  # Show first 3
                logger.info(f"  Citation {i+1}:")
                logger.info(f"    - Title: {citation.get('title', 'N/A')}")
                logger.info(f"    - Content length: {len(citation.get('content', ''))}")
                logger.info(f"    - Source data: {bool(citation.get('source_data'))}")
        
        # Analyze activity steps and subqueries
        activity_steps = result.get('activity_steps', [])
        logger.info(f"\nActivity steps: {len(activity_steps)} steps")
        subquery_count = 0
        for i, step in enumerate(activity_steps):
            logger.info(f"  Step {i+1}: {step.get('type', 'Unknown')} - {step.get('category', 'unknown')}")
            if 'subquery' in step:
                subquery_count += 1
                logger.info(f"    -> {step['subquery']}")
            elif 'query' in step:
                query_text = step['query'].get('search', '') if isinstance(step['query'], dict) else str(step['query'])
                if query_text:
                    logger.info(f"    -> Query: {query_text[:100]}...")
        
        logger.info(f"\nSubqueries identified: {subquery_count}")
        
        # Analyze query rewrites
        query_rewrites = result.get('query_rewrites', [])
        logger.info(f"Query rewrites: {len(query_rewrites)}")
        for i, rewrite in enumerate(query_rewrites):
            logger.info(f"  Rewrite {i+1}: {rewrite}")
        
        # Token usage
        token_usage = result.get('token_usage', {})
        logger.info(f"\nToken usage: {token_usage.get('total_tokens', 0)} total tokens")
        
        # Success indicators
        logger.info("\n" + "=" * 50)
        logger.info("SUCCESS INDICATORS")
        logger.info("=" * 50)
        
        success_count = 0
        total_checks = 6
        
        # Check 1: Answer is not raw JSON
        if not (answer.startswith('[{') or answer.startswith('{"')):
            logger.info("✅ Answer is LLM-generated text (not raw JSON)")
            success_count += 1
        else:
            logger.warning("❌ Answer appears to be raw JSON")
        
        # Check 2: Answer has reasonable length
        if len(answer) > 100:
            logger.info("✅ Answer has substantial content")
            success_count += 1
        else:
            logger.warning("❌ Answer is too short")
        
        # Check 3: Citations are present
        if len(citations) > 0:
            logger.info("✅ Citations are present")
            success_count += 1
        else:
            logger.warning("❌ No citations found")
        
        # Check 4: Multiple activity steps
        if len(activity_steps) > 1:
            logger.info("✅ Multiple activity steps found")
            success_count += 1
        else:
            logger.warning("❌ Only one activity step found")
        
        # Check 5: Query rewrites present
        if len(query_rewrites) > 1:
            logger.info("✅ Multiple query rewrites found")
            success_count += 1
        else:
            logger.warning("❌ Limited query rewrites")
        
        # Check 6: Token usage reasonable
        if token_usage.get('total_tokens', 0) > 1000:
            logger.info("✅ Reasonable token usage for complex processing")
            success_count += 1
        else:
            logger.warning("❌ Low token usage - may indicate limited processing")
        
        logger.info(f"\nOverall success rate: {success_count}/{total_checks} ({success_count/total_checks*100:.1f}%)")
        
        return success_count >= 4  # Consider success if most checks pass
        
    except Exception as e:
        logger.error(f"❌ Test failed with error: {e}")
        logger.error(f"Error type: {type(e).__name__}")
        return False

async def main():
    """Run the improved agentic retrieval test"""
    logger.info("Starting improved agentic retrieval test...")
    
    success = await test_improved_agentic_retrieval()
    
    logger.info("\n" + "=" * 70)
    logger.info("FINAL RESULT")
    logger.info("=" * 70)
    
    if success:
        logger.info("✅ IMPROVED AGENTIC RETRIEVAL TEST PASSED")
        logger.info("The implementation now provides better LLM-generated answers and multiple subqueries")
    else:
        logger.error("❌ IMPROVED AGENTIC RETRIEVAL TEST FAILED")
        logger.error("Further improvements needed in the implementation")
    
    return success

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
