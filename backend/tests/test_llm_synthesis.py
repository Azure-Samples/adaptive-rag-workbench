#!/usr/bin/env python3
"""
Test script for LLM synthesis functionality in agentic RAG.

This script tests the new LLM-based answer synthesis feature that generates
proper analytical answers from grounding data instead of just concatenating excerpts.
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

async def test_llm_synthesis():
    """Test LLM-based answer synthesis with the agentic RAG service."""
    
    logger.info("Starting LLM synthesis test...")
    logger.info("=" * 60)
    
    # Import and initialize the service
    from app.services.agentic_vector_rag_service import agentic_rag_service
    from app.core.config import settings
    
    # Test question
    question = "How did Microsoft's revenue perform in their latest financial results?"
    
    logger.info(f"Testing question: {question}")
    logger.info("=" * 60)
    
    try:
        # Process the question using agentic RAG
        result = await agentic_rag_service.process_question(
            question=question,
            conversation_history=[],
            rag_mode="agentic-rag"
        )
        
        logger.info("✅ AGENTIC RAG PROCESSING COMPLETED")
        logger.info("=" * 60)
        
        # Print results
        answer = result.get("answer", "No answer generated")
        citations = result.get("citations", [])
        query_rewrites = result.get("query_rewrites", [])
        activity_steps = result.get("activity_steps", [])
        
        logger.info(f"ANSWER LENGTH: {len(answer)} characters")
        logger.info(f"CITATIONS COUNT: {len(citations)}")
        logger.info(f"QUERY REWRITES COUNT: {len(query_rewrites)}")
        logger.info(f"ACTIVITY STEPS COUNT: {len(activity_steps)}")
        logger.info("")
        
        # Check if answer looks like LLM-generated content
        logger.info("🔍 ANSWER ANALYSIS:")
        logger.info("=" * 40)
        
        # Check for LLM synthesis indicators
        llm_indicators = [
            "Based on analysis",
            "According to",
            "The data shows",
            "Key findings",
            "Analysis Summary",
            "# Financial Analysis",
            "## Key Findings"
        ]
        
        has_llm_indicators = any(indicator in answer for indicator in llm_indicators)
        
        if has_llm_indicators:
            logger.info("✅ Answer appears to be LLM-synthesized (contains analytical language)")
        else:
            logger.info("⚠️ Answer may be raw concatenation (lacks analytical structure)")
        
        # Check for JSON artifacts
        has_json_artifacts = any(artifact in answer for artifact in ['{"', '[{', '"ref_id"', '"terms"'])
        
        if has_json_artifacts:
            logger.info("❌ Answer contains JSON artifacts (not properly synthesized)")
        else:
            logger.info("✅ Answer is clean (no JSON artifacts)")
        
        # Print answer preview
        logger.info("")
        logger.info("📄 ANSWER PREVIEW:")
        logger.info("=" * 40)
        answer_preview = answer[:500] + ('...' if len(answer) > 500 else '')
        logger.info(answer_preview)
        logger.info("")
        
        # Print citations preview
        logger.info("📚 CITATIONS PREVIEW:")
        logger.info("=" * 40)
        for i, citation in enumerate(citations[:3]):  # Show first 3 citations
            title = citation.get("title", "No title")
            company = citation.get("company", "No company")
            source = citation.get("source", "No source")
            logger.info(f"[{i+1}] {title} ({company}) - {source}")
        
        if len(citations) > 3:
            logger.info(f"... and {len(citations) - 3} more citations")
        
        logger.info("")
        
        # Print query rewrites
        logger.info("🔄 QUERY REWRITES:")
        logger.info("=" * 40)
        for i, rewrite in enumerate(query_rewrites[:3]):  # Show first 3 rewrites
            logger.info(f"[{i+1}] {rewrite}")
        
        if len(query_rewrites) > 3:
            logger.info(f"... and {len(query_rewrites) - 3} more rewrites")
        
        logger.info("")
        
        # Success indicators
        logger.info("🎯 SUCCESS INDICATORS:")
        logger.info("=" * 40)
        
        success_score = 0
        total_checks = 6
        
        if len(answer) > 200:
            logger.info("✅ Answer has substantial length")
            success_score += 1
        else:
            logger.info("❌ Answer is too short")
        
        if len(citations) >= 3:
            logger.info("✅ Multiple citations present")
            success_score += 1
        else:
            logger.info("❌ Insufficient citations")
        
        if len(query_rewrites) >= 2:
            logger.info("✅ Multiple query rewrites generated")
            success_score += 1
        else:
            logger.info("❌ Insufficient query rewrites")
        
        if has_llm_indicators:
            logger.info("✅ LLM synthesis indicators present")
            success_score += 1
        else:
            logger.info("❌ No LLM synthesis indicators")
        
        if not has_json_artifacts:
            logger.info("✅ Clean answer format")
            success_score += 1
        else:
            logger.info("❌ JSON artifacts present")
        
        if len(activity_steps) >= 3:
            logger.info("✅ Detailed activity steps tracked")
            success_score += 1
        else:
            logger.info("❌ Insufficient activity steps")
        
        logger.info("")
        logger.info(f"📊 OVERALL SCORE: {success_score}/{total_checks} ({success_score/total_checks*100:.1f}%)")
        
        if success_score >= 5:
            logger.info("🎉 EXCELLENT: LLM synthesis is working well!")
        elif success_score >= 3:
            logger.info("✅ GOOD: LLM synthesis is functional but could be improved")
        else:
            logger.info("❌ NEEDS WORK: LLM synthesis needs improvement")
        
        logger.info("=" * 60)
        logger.info("✅ LLM SYNTHESIS TEST COMPLETED")
        
    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        logger.error(f"Error type: {type(e).__name__}")
        raise

if __name__ == "__main__":
    asyncio.run(test_llm_synthesis())
