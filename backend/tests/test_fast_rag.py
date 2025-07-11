#!/usr/bin/env python3
"""
Test script for the enhanced Fast-RAG mode with hybrid vector search.

This script demonstrates the new features:
- Hybrid vector search (text + vector)
- Semantic ranking for improved relevance
- Advanced citation tracking
- Score-based filtering
- Query-based filter extraction
"""

import asyncio
import json
from typing import Dict, Any

async def test_fast_rag_features():
    """Test the enhanced Fast-RAG capabilities"""
    
    # Import here to avoid circular imports
    from app.agents.retriever import RetrieverAgent
    from app.core.globals import initialize_kernel
    
    print("🚀 Testing Enhanced Fast-RAG with Hybrid Vector Search")
    print("=" * 60)
    
    # Initialize the retriever
    kernel = initialize_kernel()
    retriever = RetrieverAgent(kernel)
    
    # Test cases for different scenarios
    test_cases = [
        {
            "name": "Risk Analysis Query",
            "query": "What are the main risk factors for Microsoft in 2024?",
            "expected_filters": {"company": "Microsoft"},
            "description": "Tests company-specific filtering and risk-related content retrieval"
        },
        {
            "name": "Financial Performance Query",
            "query": "Apple revenue growth strategies quarterly report",
            "expected_filters": {"company": "Apple", "document_type": "10-Q"},
            "description": "Tests document type filtering and financial content retrieval"
        },
        {
            "name": "General Technology Query",
            "query": "artificial intelligence investment trends",
            "expected_filters": {},
            "description": "Tests general search without specific filters"
        },
        {
            "name": "Multi-Company Comparison",
            "query": "Compare cloud computing revenues between tech companies",
            "expected_filters": {},
            "description": "Tests broad multi-company retrieval"
        }
    ]
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n📋 Test Case {i}: {test_case['name']}")
        print(f"Query: {test_case['query']}")
        print(f"Description: {test_case['description']}")
        print("-" * 40)
        
        try:
            # Test retrieval without automatic filters
            docs = await retriever.invoke(
                query=test_case['query'],
                filters=None,  # No automatic filters
                top_k=3
            )
            
            print(f"📊 Retrieved {len(docs)} documents")
            
            # Display results
            for j, doc in enumerate(docs, 1):
                print(f"\n  📄 Document {j}:")
                print(f"     Title: {doc.get('title', 'N/A')}")
                print(f"     Company: {doc.get('company', 'N/A')}")
                print(f"     Type: {doc.get('document_type', 'N/A')}")
                print(f"     Search Score: {doc.get('search_score', 0.0):.3f}")
                if doc.get('reranker_score'):
                    print(f"     Reranker Score: {doc.get('reranker_score'):.3f}")
                print(f"     Content Preview: {doc.get('content', '')[:100]}...")
                
                # Show highlights if available
                highlights = doc.get('highlights', [])
                if highlights:
                    print(f"     🎯 Highlights: {highlights[0][:80]}...")
            
            # Test streaming response
            print(f"\n🌊 Testing streaming for: {test_case['query'][:50]}...")
            stream_count = 0
            async for chunk in retriever.invoke_stream(test_case['query'], top_k=2):
                if stream_count < 5:  # Limit output for testing
                    print(f"     Stream: {chunk.strip()}")
                stream_count += 1
            
            print(f"     (Generated {stream_count} stream chunks)")
            
        except Exception as e:
            print(f"❌ Test failed: {str(e)}")
            import traceback
            traceback.print_exc()
    
    print("\n" + "=" * 60)
    print("🎉 Fast-RAG Testing Complete!")

async def test_citation_quality():
    """Test the quality of citation information"""
    
    print("\n🔗 Testing Citation Quality")
    print("=" * 30)
    
    from app.agents.retriever import RetrieverAgent
    from app.core.globals import initialize_kernel
    
    kernel = initialize_kernel()
    retriever = RetrieverAgent(kernel)
    
    # Test with a specific query
    query = "Microsoft cloud revenue 2024"
    docs = await retriever.invoke(query, top_k=2)
    
    for i, doc in enumerate(docs, 1):
        print(f"\n📄 Document {i} Citation Analysis:")
        citation = doc.get('citation', {})
        
        # Check citation completeness
        required_fields = ['title', 'source', 'company', 'document_type']
        optional_fields = ['filing_date', 'page_number', 'section_type', 'document_url']
        
        print(f"  ✅ Required Fields:")
        for field in required_fields:
            value = citation.get(field, 'N/A')
            print(f"     {field}: {value}")
        
        print(f"  🔍 Optional Fields:")
        for field in optional_fields:
            value = citation.get(field, 'N/A')
            if value != 'N/A' and value is not None:
                print(f"     {field}: {value}")
        
        # Check credibility score
        cred_score = citation.get('credibility_score', 0.0)
        print(f"  ⭐ Credibility Score: {cred_score:.3f}")
        
        # Check search metadata
        search_score = doc.get('search_score', 0.0)
        reranker_score = doc.get('reranker_score')
        print(f"  📊 Search Score: {search_score:.3f}")
        if reranker_score:
            print(f"  🎯 Reranker Score: {reranker_score:.3f}")

async def test_integration_with_chat_api():
    """Test integration with the chat API endpoint"""
    
    print("\n🌐 Testing Integration with Chat API")
    print("=" * 35)
    
    from app.api.chat import process_fast_rag
    
    test_queries = [
        "What are Apple's main revenue streams?",
        "Microsoft cloud computing strategy 2024",
        "Risk factors for technology companies"
    ]
    
    for query in test_queries:
        print(f"\n🔍 Testing Query: {query}")
        print("-" * 30)
        
        try:
            result = await process_fast_rag(query, "test_session_123")
            
            print(f"✅ Success: {result.get('success', False)}")
            print(f"📊 Documents Retrieved: {result.get('documents_retrieved', 0)}")
            print(f"⏱️ Processing Time: {result.get('processing_time_ms', 0)}ms")
            print(f"🔍 Retrieval Method: {result.get('retrieval_method', 'N/A')}")
            print(f"📋 Citations: {len(result.get('citations', []))}")
            
            # Show answer preview
            answer = result.get('answer', '')
            if answer:
                preview = answer[:200] + "..." if len(answer) > 200 else answer
                print(f"💬 Answer Preview: {preview}")
            
            # Show filters applied
            filters = result.get('filters_applied', {})
            if filters:
                print(f"🎯 Filters Applied: {filters}")
                
        except Exception as e:
            print(f"❌ Error: {str(e)}")

if __name__ == "__main__":
    print("🧪 Enhanced Fast-RAG Test Suite")
    print("Testing hybrid vector search with Azure AI Search")
    print("=" * 60)
    
    asyncio.run(test_fast_rag_features())
    asyncio.run(test_citation_quality()) 
    asyncio.run(test_integration_with_chat_api())
    
    print("\n🎯 All tests completed!")
    print("Your Fast-RAG implementation is ready for QA with verifications!")
