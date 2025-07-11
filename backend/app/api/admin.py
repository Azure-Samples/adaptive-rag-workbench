from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import JSONResponse
from typing import Dict, Any
from ..services.azure_services import get_azure_service_manager
from ..auth.middleware import get_current_user

router = APIRouter()

@router.post("/admin/search-index/recreate")
async def recreate_search_index(current_user: dict = Depends(get_current_user)):
    """
    Recreate the search index with updated schema (facetable fields).
    WARNING: This will delete all existing data in the index.
    """
    try:
        azure_service_manager = await get_azure_service_manager()
        
        # Check current index status
        current_stats = await azure_service_manager.get_index_stats()
        
        if current_stats.get("total_documents", 0) > 0:
            return JSONResponse(
                status_code=400,
                content={
                    "error": "Index contains data",
                    "message": "The index contains documents. Recreating will delete all data.",
                    "current_document_count": current_stats.get("total_documents", 0),
                    "company_breakdown": current_stats.get("company_breakdown", {}),
                    "recommendation": "Please confirm you want to proceed by calling /admin/search-index/recreate-confirm"
                }
            )
        
        # If no documents, proceed with recreation
        result = await azure_service_manager.recreate_search_index_with_facetable_fields()
        
        if result:
            return {
                "success": True,
                "message": "Search index successfully recreated with facetable fields",
                "next_steps": [
                    "Re-ingest your documents using the /ingest endpoint",
                    "Verify the index schema with /admin/search-index/schema"
                ]
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to recreate search index")
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/admin/search-index/recreate-confirm")
async def recreate_search_index_confirm(current_user: dict = Depends(get_current_user)):
    """
    Force recreate the search index even if it contains data.
    This will permanently delete all existing documents.
    """
    try:
        azure_service_manager = await get_azure_service_manager()
        
        # Get current stats before deletion
        current_stats = await azure_service_manager.get_index_stats()
        
        result = await azure_service_manager.recreate_search_index_with_facetable_fields()
        
        if result:
            return {
                "success": True,
                "message": "Search index forcefully recreated",
                "deleted_documents": current_stats.get("total_documents", 0),
                "deleted_companies": len(current_stats.get("company_breakdown", {})),
                "next_steps": [
                    "Re-ingest your documents using the /ingest endpoint",
                    "Verify the index schema with /admin/search-index/schema"
                ]
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to recreate search index")
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/admin/search-index/schema")
async def get_search_index_schema(current_user: dict = Depends(get_current_user)):
    """Get the current search index schema"""
    try:
        azure_service_manager = await get_azure_service_manager()
        
        # Get the current index schema
        try:
            from ..core.config import settings
            existing_index = azure_service_manager.search_index_client.get_index(settings.search_index)
            
            fields_info = []
            for field in existing_index.fields:
                field_info = {
                    "name": field.name,
                    "type": str(field.type),
                    "key": getattr(field, 'key', False),
                    "searchable": getattr(field, 'searchable', False),
                    "filterable": getattr(field, 'filterable', False),
                    "facetable": getattr(field, 'facetable', False),
                    "sortable": getattr(field, 'sortable', False)
                }
                fields_info.append(field_info)
            
            # Check for facetable fields
            facetable_fields = [f for f in fields_info if f['facetable']]
            
            return {
                "index_name": settings.search_index,
                "total_fields": len(fields_info),
                "fields": fields_info,
                "facetable_fields": facetable_fields,
                "facetable_field_names": [f['name'] for f in facetable_fields],
                "schema_version": "enhanced_with_facets" if facetable_fields else "basic"
            }
            
        except Exception as e:
            return {
                "error": f"Could not retrieve index schema: {str(e)}",
                "index_name": settings.search_index,
                "exists": False
            }
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/admin/search-index/test-facets")
async def test_facets(current_user: dict = Depends(get_current_user)):
    """Test if facets are working correctly"""
    try:
        azure_service_manager = await get_azure_service_manager()
        
        # Test different facet fields
        facet_tests = {}
        
        for field in ["company", "document_type", "form_type", "industry"]:
            try:
                results = azure_service_manager.search_client.search(
                    "*",
                    facets=[field],
                    top=0
                )
                
                facets = results.get_facets()
                if facets and field in facets:
                    facet_tests[field] = {
                        "working": True,
                        "facet_count": len(facets[field]),
                        "top_values": facets[field][:5]  # Top 5 values
                    }
                else:
                    facet_tests[field] = {
                        "working": False,
                        "error": "No facets returned"
                    }
                    
            except Exception as e:
                facet_tests[field] = {
                    "working": False,
                    "error": str(e)
                }
        
        return {
            "facet_tests": facet_tests,
            "overall_status": "working" if all(t.get("working", False) for t in facet_tests.values()) else "needs_attention"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
