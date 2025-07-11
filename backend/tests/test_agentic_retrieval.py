#!/usr/bin/env python3
"""
Test script for enhanced Agentic RAG functionality
Tests the full agentic retrieval pipeline with Azure AI Search Knowledge Agent
"""

import asyncio
import sys
import os
import json
from datetime import datetime

# Add the backend directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from app.services.agentic_vector_rag_service import agentic_rag_service
from app.core.config import settings

async def test_agentic_retrieval():
    """Test the enhanced agentic retrieval functionality"""
    
    print("=== Testing Enhanced Agentic RAG Implementation ===\n")
    
    # Initialize the service
    print("1. Initializing Agentic RAG Service...")
    await agentic_rag_service.initialize()
    
    # Get diagnostics
    print("2. Service Diagnostics:")
    diagnostics = await agentic_rag_service.get_diagnostics()
    print(json.dumps(diagnostics, indent=2))
    
    # Test questions covering different aspects
    test_questions = [
        {
            "question": "What are the key risk factors for tech companies in the current market environment?",
            "conversation_history": None,
            "description": "Complex question requiring analysis across multiple documents"
        },
        {
            "question": "How did Microsoft's cloud revenue perform in the last quarter?",
            "conversation_history": [
                {"role": "user", "content": "Can you tell me about Microsoft's recent earnings?"},
                {"role": "assistant", "content": "I can help you with Microsoft's recent earnings information. What specific aspects would you like to know about?"}
            ],
            "description": "Specific financial query with conversation context"
        },
        {
            "question": "Compare the growth strategies of major cloud providers and their market positioning",
            "conversation_history": None,
            "description": "Multi-company comparison requiring complex analysis"
        }
    ]
    
    print("\n3. Testing Agentic Retrieval Pipeline...")
    
    for i, test_case in enumerate(test_questions, 1):
        print(f"\n--- Test Case {i}: {test_case['description']} ---")
        print(f"Question: {test_case['question']}")
        
        try:
            # Test agentic retrieval
            result = await agentic_rag_service.process_question(
                question=test_case['question'],
                conversation_history=test_case['conversation_history'],
                rag_mode="agentic-rag"
            )
            
            print(f"✅ Success: {result['success']}")
            print(f"📊 Retrieval Method: {result['retrieval_method']}")
            print(f"⏱️  Processing Time: {result['processing_time_ms']}ms")
            print(f"📄 Citations: {len(result['citations'])}")
            print(f"🔄 Query Rewrites: {len(result['query_rewrites'])}")
            print(f"🎯 Activity Steps: {len(result.get('activity_steps', []))}")
            
            # Show token usage
            if 'token_usage' in result:
                token_usage = result['token_usage']
                print(f"💰 Token Usage:")
                print(f"   - Prompt tokens: {token_usage.get('prompt_tokens', 0)}")
                print(f"   - Completion tokens: {token_usage.get('completion_tokens', 0)}")
                print(f"   - Total tokens: {token_usage.get('total_tokens', 0)}")
                if 'query_planning_tokens' in token_usage:
                    print(f"   - Query planning tokens: {token_usage.get('query_planning_tokens', 0)}")
                if 'semantic_ranking_tokens' in token_usage:
                    print(f"   - Semantic ranking tokens: {token_usage.get('semantic_ranking_tokens', 0)}")
            
            # Show query rewrites (subqueries)
            if result['query_rewrites']:
                print(f"🔄 Query Rewrites (Subqueries):")
                for j, rewrite in enumerate(result['query_rewrites'], 1):
                    print(f"   {j}. {rewrite}")
            
            # Show activity steps
            if result.get('activity_steps'):
                print(f"🎯 Activity Steps:")
                for step in result['activity_steps']:
                    step_type = step.get('type', 'Unknown')
                    step_id = step.get('id', '?')
                    print(f"   {step_id}. {step_type}")
                    if 'query' in step:
                        query_info = step['query']
                        if isinstance(query_info, dict) and 'search' in query_info:
                            print(f"      Query: {query_info['search']}")
                    if 'input_tokens' in step:
                        print(f"      Input tokens: {step['input_tokens']}")
                    if 'output_tokens' in step:
                        print(f"      Output tokens: {step['output_tokens']}")
                    if 'elapsed_ms' in step:
                        print(f"      Elapsed: {step['elapsed_ms']}ms")
            
            # Show top citations
            if result['citations']:
                print(f"📚 Top Citations:")
                for j, citation in enumerate(result['citations'][:3], 1):
                    print(f"   {j}. {citation.get('title', 'No title')}")
                    print(f"      Source: {citation.get('source', 'Unknown')}")
                    print(f"      Doc Key: {citation.get('doc_key', 'Unknown')}")
                    if 'search_score' in citation:
                        print(f"      Search Score: {citation['search_score']:.3f}")
                    if 'reranker_score' in citation:
                        print(f"      Reranker Score: {citation['reranker_score']:.3f}")
            
            # Show answer preview
            answer = result.get('answer', '')
            if answer:
                preview = answer[:300] + "..." if len(answer) > 300 else answer
                print(f"💬 Answer Preview: {preview}")
            
            print(f"📈 Processing Details:")
            if 'processing_details' in result:
                details = result['processing_details']
                for key, value in details.items():
                    print(f"   - {key}: {value}")
            
        except Exception as e:
            print(f"❌ Error: {e}")
            import traceback
            traceback.print_exc()
    
    print("\n=== Agentic RAG Testing Complete ===")
    
    # Test diagnostics
    print("\n4. Final Diagnostics:")
    final_diagnostics = await agentic_rag_service.get_diagnostics()
    print(json.dumps(final_diagnostics, indent=2))

if __name__ == "__main__":
    print(f"Starting Agentic RAG tests at {datetime.now()}")
    print(f"Azure Search Endpoint: {settings.search_endpoint}")
    print(f"Search Index: {settings.search_index}")
    print(f"OpenAI Endpoint: {settings.openai_endpoint}")
    print(f"Chat Deployment: {settings.openai_chat_deployment}")
    print()
    
    asyncio.run(test_agentic_retrieval())
