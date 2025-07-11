#!/usr/bin/env python3
"""
Detailed test of working agentic retrieval
"""

import asyncio
import sys
import os
import json

# Add the backend directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from app.services.agentic_vector_rag_service import agentic_rag_service

async def test_agentic_detailed():
    """Test agentic retrieval with detailed output"""
    
    print("=== Detailed Agentic RAG Test ===\n")
    
    # Initialize the service
    print("1. Initializing Agentic RAG Service...")
    await agentic_rag_service.initialize()
    print("✅ Service initialized successfully")
    
    # Test a financial question
    test_question = "What are Microsoft's key risk factors mentioned in their latest 10-K filing?"
    
    print(f"\n2. Testing question: {test_question}")
    result = await agentic_rag_service.process_question(
        question=test_question,
        rag_mode="agentic-rag"
    )
    
    print("=== FULL RESULT ===")
    print(json.dumps(result, indent=2, default=str))
    
    print("\n=== KEY METRICS ===")
    print(f"✅ Success: {result.get('success')}")
    print(f"🔧 Retrieval Method: {result.get('retrieval_method')}")
    print(f"⏱️  Processing Time: {result.get('processing_time_ms')}ms")
    print(f"📄 Citations: {len(result.get('citations', []))}")
    print(f"🔄 Query Rewrites: {len(result.get('query_rewrites', []))}")
    print(f"🎯 Activity Steps: {len(result.get('activity_steps', []))}")
    
    # Show the actual answer
    answer = result.get('answer', '')
    print(f"\n📝 Answer Length: {len(answer)} characters")
    print(f"📝 Answer Preview: {answer[:500]}...")
    
    # Show citations
    citations = result.get('citations', [])
    if citations:
        print(f"\n📚 Citations ({len(citations)}):")
        for i, citation in enumerate(citations[:3], 1):
            print(f"   {i}. {citation}")
    
    # Show query rewrites
    query_rewrites = result.get('query_rewrites', [])
    if query_rewrites:
        print(f"\n🔄 Query Rewrites ({len(query_rewrites)}):")
        for i, rewrite in enumerate(query_rewrites, 1):
            print(f"   {i}. {rewrite}")
    
    # Show activity steps
    activity_steps = result.get('activity_steps', [])
    if activity_steps:
        print(f"\n🎯 Activity Steps ({len(activity_steps)}):")
        for step in activity_steps:
            print(f"   - {step}")

if __name__ == "__main__":
    asyncio.run(test_agentic_detailed())
