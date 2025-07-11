#!/usr/bin/env python3
"""
Debug script to examine citation extraction in detail.
"""

import asyncio
import logging
import os
import sys
import json

# Add the backend directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def debug_citations():
    """Debug citation extraction in detail."""
    
    logger.info("Debugging citation extraction...")
    logger.info("=" * 60)
    
    # Import and initialize the service
    from app.services.agentic_vector_rag_service import agentic_rag_service
    from app.services.agentic_vector_rag_service import KnowledgeAgentIndexParams, KnowledgeAgentRetrievalRequest
    from app.core.config import settings
    
    # Test question
    question = "What is Microsoft's revenue?"
    
    try:
        # Initialize the service
        await agentic_rag_service.initialize()
        
        # Get the raw response
        messages = agentic_rag_service._build_conversation_messages(question, None)
        
        index_params = KnowledgeAgentIndexParams(
            index_name=settings.search_index,
            reranker_threshold=1.0
        )
        
        request = KnowledgeAgentRetrievalRequest(
            messages=messages,
            target_index_params=[index_params]
        )
        
        response = agentic_rag_service.knowledge_agent_client.retrieve(request)
        
        logger.info("=" * 40)
        logger.info("RAW CITATION DEBUG")
        logger.info("=" * 40)
        
        # Check references
        if hasattr(response, 'references') and response.references:
            logger.info(f"Found {len(response.references)} references")
            
            for i, ref in enumerate(response.references):
                logger.info(f"\n--- REFERENCE {i+1} ---")
                logger.info(f"Reference type: {type(ref)}")
                logger.info(f"Reference attributes: {[attr for attr in dir(ref) if not attr.startswith('_')]}")
                
                # Check doc_key
                if hasattr(ref, 'doc_key'):
                    logger.info(f"doc_key: {getattr(ref, 'doc_key', 'None')}")
                
                # Check source_data
                if hasattr(ref, 'source_data'):
                    source_data = getattr(ref, 'source_data', None)
                    logger.info(f"source_data type: {type(source_data)}")
                    
                    if source_data:
                        if isinstance(source_data, dict):
                            logger.info(f"source_data keys: {list(source_data.keys())}")
                            for key in ['title', 'company', 'content', 'document_type', 'source']:
                                if key in source_data:
                                    value = source_data[key]
                                    logger.info(f"  {key}: {value[:100] if isinstance(value, str) else value}")
                        elif isinstance(source_data, str):
                            logger.info(f"source_data length: {len(source_data)}")
                            logger.info(f"source_data preview: {source_data[:200]}")
                            
                            # Try to parse as JSON
                            try:
                                parsed_data = json.loads(source_data)
                                logger.info(f"parsed JSON keys: {list(parsed_data.keys()) if isinstance(parsed_data, dict) else 'not dict'}")
                            except:
                                logger.info("source_data is not valid JSON")
                        else:
                            logger.info(f"source_data value: {source_data}")
                    else:
                        logger.info("source_data is None/empty")
                
                # Check other attributes
                for attr in ['id', 'title', 'content', 'url', 'score']:
                    if hasattr(ref, attr):
                        value = getattr(ref, attr)
                        logger.info(f"{attr}: {value[:100] if isinstance(value, str) and len(str(value)) > 100 else value}")
        
        else:
            logger.info("No references found in response")
        
        # Test citation formatting
        logger.info("\n" + "=" * 40)
        logger.info("FORMATTED CITATIONS DEBUG")
        logger.info("=" * 40)
        
        citations = agentic_rag_service._format_citations_from_references(
            response.references if hasattr(response, 'references') else []
        )
        
        for i, citation in enumerate(citations):
            logger.info(f"\n--- CITATION {i+1} ---")
            for key, value in citation.items():
                if isinstance(value, str) and len(value) > 100:
                    logger.info(f"{key}: {value[:100]}...")
                else:
                    logger.info(f"{key}: {value}")
        
        logger.info("\n" + "=" * 60)
        logger.info("✅ CITATION DEBUG COMPLETED")
        
    except Exception as e:
        logger.error(f"❌ Debug failed: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(debug_citations())
