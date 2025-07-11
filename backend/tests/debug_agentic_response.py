#!/usr/bin/env python3
"""
Debug script to inspect the raw agentic response structure
to understand how to extract the LLM-generated answer properly.
"""

import asyncio
import sys
import os
import logging
import json
from pathlib import Path

# Add the backend directory to the path
sys.path.insert(0, str(Path(__file__).parent))

from app.services.agentic_vector_rag_service import agentic_rag_service

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def debug_agentic_response():
    """Debug the raw agentic response structure"""
    
    test_question = "What is Microsoft's revenue?"
    
    logger.info("=" * 60)
    logger.info("DEBUGGING AGENTIC RESPONSE STRUCTURE")
    logger.info("=" * 60)
    
    try:
        # Initialize the service
        await agentic_rag_service.initialize()
        
        # Get the raw response by calling the retrieval method directly
        messages = agentic_rag_service._build_conversation_messages(test_question, None)
        
        # Import the required classes
        from app.services.agentic_vector_rag_service import KnowledgeAgentIndexParams, KnowledgeAgentRetrievalRequest
        from app.core.config import settings
        
        index_params = KnowledgeAgentIndexParams(
            index_name=settings.search_index,
            reranker_threshold=1.0
        )
        
        request = KnowledgeAgentRetrievalRequest(
            messages=messages,
            target_index_params=[index_params]
        )
        
        logger.info("Executing raw agentic retrieval...")
        response = agentic_rag_service.knowledge_agent_client.retrieve(request)
        
        logger.info("=" * 40)
        logger.info("RAW RESPONSE STRUCTURE")
        logger.info("=" * 40)
        
        # Debug the response structure
        logger.info(f"Response type: {type(response)}")
        logger.info(f"Response dir: {[attr for attr in dir(response) if not attr.startswith('_')]}")
        
        # Check for response attribute
        if hasattr(response, 'response'):
            logger.info(f"Response.response type: {type(response.response)}")
            if response.response:
                logger.info(f"Response.response length: {len(response.response) if isinstance(response.response, list) else 'not list'}")
                if isinstance(response.response, list) and len(response.response) > 0:
                    first_resp = response.response[0]
                    logger.info(f"First response type: {type(first_resp)}")
                    logger.info(f"First response dir: {[attr for attr in dir(first_resp) if not attr.startswith('_')]}")
                    
                    if hasattr(first_resp, 'content'):
                        logger.info(f"First response content type: {type(first_resp.content)}")
                        if isinstance(first_resp.content, list):
                            logger.info(f"Content list length: {len(first_resp.content)}")
                            if len(first_resp.content) > 0:
                                content_item = first_resp.content[0]
                                logger.info(f"Content item type: {type(content_item)}")
                                logger.info(f"Content item dir: {[attr for attr in dir(content_item) if not attr.startswith('_')]}")
                                
                                if hasattr(content_item, 'text'):
                                    text = content_item.text
                                    logger.info(f"Content text type: {type(text)}")
                                    logger.info(f"Content text length: {len(text) if text else 0}")
                                    if text:
                                        logger.info(f"Content text preview: {text[:200]}...")
        
        # Check for other possible response formats
        for attr in ['answer', 'content', 'text', 'data', 'result']:
            if hasattr(response, attr):
                value = getattr(response, attr)
                logger.info(f"Response.{attr} type: {type(value)}")
                if isinstance(value, str):
                    logger.info(f"Response.{attr} length: {len(value)}")
                    logger.info(f"Response.{attr} preview: {value[:200]}...")
        
        # Check references
        if hasattr(response, 'references'):
            logger.info(f"References count: {len(response.references) if response.references else 0}")
            if response.references and len(response.references) > 0:
                ref = response.references[0]
                logger.info(f"First reference type: {type(ref)}")
                logger.info(f"First reference dir: {[attr for attr in dir(ref) if not attr.startswith('_')]}")
        
        # Try to serialize the response
        try:
            logger.info("=" * 40)
            logger.info("ATTEMPTING JSON SERIALIZATION")
            logger.info("=" * 40)
            
            # Try to convert response to dict for JSON serialization
            response_dict = {}
            for attr in dir(response):
                if not attr.startswith('_'):
                    try:
                        value = getattr(response, attr)
                        if not callable(value):
                            response_dict[attr] = str(value)[:100]  # Limit length
                    except:
                        pass
            
            logger.info(f"Response attributes: {json.dumps(response_dict, indent=2)}")
            
        except Exception as e:
            logger.warning(f"Could not serialize response: {e}")
        
        return True
        
    except Exception as e:
        logger.error(f"Debug failed: {e}")
        return False

async def main():
    """Run the debug"""
    logger.info("Starting agentic response structure debug...")
    
    success = await debug_agentic_response()
    
    if success:
        logger.info("✅ DEBUG COMPLETED")
    else:
        logger.error("❌ DEBUG FAILED")
    
    return success

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
