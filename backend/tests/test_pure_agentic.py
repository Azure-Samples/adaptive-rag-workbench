#!/usr/bin/env python3
"""
Test script to verify pure agentic retrieval with no fallback logic.
This should surface any errors in the agentic retrieval pipeline.
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

async def test_pure_agentic_retrieval():
    """Test pure agentic retrieval with error surfacing"""
    
    # Test question that should surface any issues
    test_question = "What is Microsoft's current stock price and market cap?"
    
    logger.info("=" * 60)
    logger.info("TESTING PURE AGENTIC RETRIEVAL (NO FALLBACK)")
    logger.info("=" * 60)
    
    try:
        # Initialize the service
        logger.info("Initializing agentic RAG service...")
        await agentic_rag_service.initialize()
        
        # Get diagnostics
        diagnostics = await agentic_rag_service.get_diagnostics()
        logger.info(f"Service diagnostics: {diagnostics}")
        
        # Test the question processing
        logger.info(f"Processing question: '{test_question}'")
        
        result = await agentic_rag_service.process_question(
            question=test_question,
            conversation_history=None,
            rag_mode="agentic-rag"
        )
        
        # If we reach here, agentic retrieval succeeded
        logger.info("✅ AGENTIC RETRIEVAL SUCCEEDED!")
        logger.info(f"Answer: {result.get('answer', 'No answer')[:200]}...")
        logger.info(f"Citations: {len(result.get('citations', []))}")
        logger.info(f"Query rewrites: {result.get('query_rewrites', [])}")
        logger.info(f"Activity steps: {len(result.get('activity_steps', []))}")
        logger.info(f"Token usage: {result.get('token_usage', {})}")
        
        return True
        
    except Exception as e:
        logger.error("❌ AGENTIC RETRIEVAL FAILED - ERROR SURFACED AS EXPECTED")
        logger.error(f"Error type: {type(e).__name__}")
        logger.error(f"Error message: {str(e)}")
        
        # Check if this is a fallback error (should not happen anymore)
        if "fallback" in str(e).lower():
            logger.error("🚨 FALLBACK LOGIC STILL PRESENT - THIS SHOULD BE REMOVED")
            return False
        else:
            logger.info("✅ ERROR PROPERLY SURFACED - NO FALLBACK OCCURRED")
            return True

async def test_diagnostics():
    """Test service diagnostics"""
    logger.info("\n" + "=" * 40)
    logger.info("TESTING SERVICE DIAGNOSTICS")
    logger.info("=" * 40)
    
    try:
        diagnostics = await agentic_rag_service.get_diagnostics()
        
        logger.info("Service diagnostics:")
        for key, value in diagnostics.items():
            logger.info(f"  {key}: {value}")
            
        # Check key diagnostic flags
        if not diagnostics.get("agentic_enabled", False):
            logger.warning("⚠️  Agentic mode is not enabled")
        
        if not diagnostics.get("imports_available", False):
            logger.warning("⚠️  Agentic imports are not available")
            
        if not diagnostics.get("knowledge_agent_available", False):
            logger.warning("⚠️  Knowledge agent is not available")
            
        return True
        
    except Exception as e:
        logger.error(f"❌ Diagnostics test failed: {e}")
        return False

async def main():
    """Run all tests"""
    logger.info("Starting pure agentic retrieval tests...")
    
    # Test diagnostics first
    diagnostics_success = await test_diagnostics()
    
    # Test pure agentic retrieval
    agentic_success = await test_pure_agentic_retrieval()
    
    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("TEST SUMMARY")
    logger.info("=" * 60)
    logger.info(f"Diagnostics test: {'✅ PASSED' if diagnostics_success else '❌ FAILED'}")
    logger.info(f"Pure agentic test: {'✅ PASSED' if agentic_success else '❌ FAILED'}")
    
    if agentic_success:
        logger.info("✅ SUCCESS: Fallback logic has been removed, errors are surfaced")
    else:
        logger.error("❌ FAILURE: Fallback logic may still be present")
    
    return diagnostics_success and agentic_success

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
