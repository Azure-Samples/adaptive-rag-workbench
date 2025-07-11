#!/usr/bin/env python3
"""
Test script to force agentic retrieval errors and fix them
"""

import asyncio
import sys
import os

# Add the backend directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from app.services.agentic_vector_rag_service import agentic_rag_service

async def test_agentic_errors():
    """Test agentic retrieval to see actual errors"""
    
    print("=== Testing Agentic RAG - No Fallback ===\n")
    
    # Initialize the service
    print("1. Initializing Agentic RAG Service...")
    try:
        await agentic_rag_service.initialize()
        print("✅ Service initialized successfully")
    except Exception as e:
        print(f"❌ Initialization error: {e}")
        print(f"Error type: {type(e).__name__}")
        import traceback
        traceback.print_exc()
        return
    
    # Test a simple question
    test_question = "What is Microsoft's current stock price and market cap?"
    
    print(f"\n2. Testing question: {test_question}")
    try:
        result = await agentic_rag_service.process_question(
            question=test_question,
            rag_mode="agentic-rag"
        )
        print("✅ Question processed successfully")
        print(f"Answer: {result.get('answer', 'No answer')[:200]}...")
        
    except Exception as e:
        print(f"❌ Query processing error: {e}")
        print(f"Error type: {type(e).__name__}")
        import traceback
        traceback.print_exc()
    
    # Get diagnostics
    print("\n3. Service Diagnostics:")
    try:
        diagnostics = await agentic_rag_service.get_diagnostics()
        for key, value in diagnostics.items():
            print(f"   {key}: {value}")
    except Exception as e:
        print(f"❌ Diagnostics error: {e}")

if __name__ == "__main__":
    asyncio.run(test_agentic_errors())
