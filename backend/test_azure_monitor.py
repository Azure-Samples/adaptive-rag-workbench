#!/usr/bin/env python3
"""
Test script to verify Azure AI Project service initialization and Azure Monitor tracing
"""

import asyncio
import logging
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '.'))

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

async def test_azure_monitor_initialization():
    """Test Azure AI Project service initialization"""
    print("Testing Azure AI Project service initialization...")
    
    try:
        from app.services.azure_ai_project_service import azure_ai_project_service
        
        print("Initializing Azure AI Project service...")
        await azure_ai_project_service.initialize()
        
        print(f"Instrumented: {azure_ai_project_service.is_instrumented()}")
        print(f"Chat client type: {type(azure_ai_project_service.get_chat_client())}")
        print(f"Project client type: {type(azure_ai_project_service.get_project_client())}")
        
        if azure_ai_project_service.is_instrumented():
            print("✅ Azure AI Project service initialized successfully with telemetry")
            return True
        else:
            print("❌ Azure AI Project service not properly instrumented")
            return False
            
    except Exception as e:
        print(f"❌ Error initializing Azure AI Project service: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_azure_services_manager():
    """Test Azure Services Manager initialization"""
    print("\nTesting Azure Services Manager initialization...")
    
    try:
        from app.services.azure_services import azure_service_manager
        
        print("Initializing Azure Services Manager...")
        await azure_service_manager.initialize()
        
        print(f"OpenAI client type: {type(azure_service_manager.async_openai_client)}")
        print(f"Search client available: {azure_service_manager.search_client is not None}")
        
        if azure_service_manager.async_openai_client is not None:
            print("✅ Azure Services Manager initialized successfully")
            return True
        else:
            print("❌ Azure Services Manager OpenAI client not available")
            return False
            
    except Exception as e:
        print(f"❌ Error initializing Azure Services Manager: {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    """Main test function"""
    print("=== Azure Monitor Tracing Verification ===\n")
    
    project_service_ok = await test_azure_monitor_initialization()
    
    services_manager_ok = await test_azure_services_manager()
    
    print("\n=== Test Results ===")
    print(f"Azure AI Project Service: {'✅ PASS' if project_service_ok else '❌ FAIL'}")
    print(f"Azure Services Manager: {'✅ PASS' if services_manager_ok else '❌ FAIL'}")
    
    if project_service_ok and services_manager_ok:
        print("\n🎉 All tests passed! Azure Monitor tracing should be working.")
    else:
        print("\n⚠️  Some tests failed. Azure Monitor tracing may not be working properly.")

if __name__ == "__main__":
    asyncio.run(main())
