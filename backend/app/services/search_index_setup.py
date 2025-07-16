import asyncio
import logging
from azure.search.documents.indexes.aio import SearchIndexClient
from azure.search.documents.indexes.models import (
    SearchIndex, SearchField, SearchFieldDataType, VectorSearch,
    VectorSearchProfile, HnswAlgorithmConfiguration
)
from azure.core.credentials import AzureKeyCredential
from ..core.config import settings

logger = logging.getLogger(__name__)

async def setup_vector_search_index():
    """Set up Azure Search index with vector search capabilities"""
    try:
        index_client = SearchIndexClient(
            endpoint=settings.search_endpoint,
            credential=AzureKeyCredential(settings.search_admin_key)
        )
        
        fields = [
            SearchField(name="id", type=SearchFieldDataType.String, key=True),
            SearchField(name="content", type=SearchFieldDataType.String, searchable=True),
            SearchField(name="title", type=SearchFieldDataType.String, searchable=True),
            SearchField(name="document_id", type=SearchFieldDataType.String, filterable=True),
            SearchField(name="source", type=SearchFieldDataType.String, filterable=True),
            SearchField(name="document_type", type=SearchFieldDataType.String, filterable=True),
            SearchField(name="company", type=SearchFieldDataType.String, filterable=True, facetable=True),
            SearchField(name="year", type=SearchFieldDataType.String, filterable=True, facetable=True),
            SearchField(name="filing_date", type=SearchFieldDataType.String, filterable=True, sortable=True),
            SearchField(name="section_type", type=SearchFieldDataType.String, filterable=True, facetable=True),
            SearchField(name="chunk_index", type=SearchFieldDataType.Int32, filterable=True, sortable=True),
            SearchField(name="content_length", type=SearchFieldDataType.Int32, filterable=True, sortable=True),
            SearchField(name="word_count", type=SearchFieldDataType.Int32, filterable=True, sortable=True),
            SearchField(name="content_vector", type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
                       vector_search_dimensions=1536, vector_search_profile_name="vector-profile"),
            SearchField(name="credibility_score", type=SearchFieldDataType.Double, filterable=True, sortable=True),
            SearchField(name="citation_info", type=SearchFieldDataType.String),
            SearchField(name="has_structured_content", type=SearchFieldDataType.Boolean, filterable=True),
            SearchField(name="structure_info", type=SearchFieldDataType.String),
            SearchField(name="chunk_id", type=SearchFieldDataType.String, filterable=True),
            SearchField(name="embedding_model", type=SearchFieldDataType.String, filterable=True),
            SearchField(name="embedding_dimensions", type=SearchFieldDataType.Int32, filterable=True)
        ]
        
        vector_search = VectorSearch(
            profiles=[
                VectorSearchProfile(
                    name="vector-profile",
                    algorithm_configuration_name="vector-config"
                )
            ],
            algorithms=[
                HnswAlgorithmConfiguration(
                    name="vector-config"
                )
            ]
        )
        
        index = SearchIndex(
            name=settings.search_index_upload,
            fields=fields,
            vector_search=vector_search
        )
        
        result = await index_client.create_or_update_index(index)
        logger.info(f"Successfully created/updated search index: {result.name}")
        
        await index_client.close()
        return True
        
    except Exception as e:
        logger.error(f"Error setting up vector search index: {e}")
        raise

async def delete_search_index():
    """Delete the search index (useful for testing)"""
    try:
        index_client = SearchIndexClient(
            endpoint=settings.search_endpoint,
            credential=AzureKeyCredential(settings.search_admin_key)
        )
        
        await index_client.delete_index(settings.search_index_upload)
        logger.info(f"Successfully deleted search index: {settings.search_index_upload}")
        
        await index_client.close()
        return True
        
    except Exception as e:
        logger.error(f"Error deleting search index: {e}")
        raise

async def get_index_stats():
    """Get statistics about the search index"""
    try:
        index_client = SearchIndexClient(
            endpoint=settings.search_endpoint,
            credential=AzureKeyCredential(settings.search_admin_key)
        )
        
        index = await index_client.get_index(settings.search_index_upload)
        
        stats = {
            "name": index.name,
            "fields_count": len(index.fields),
            "vector_search_enabled": index.vector_search is not None,
            "fields": [{"name": field.name, "type": str(field.type)} for field in index.fields]
        }
        
        await index_client.close()
        return stats
        
    except Exception as e:
        logger.error(f"Error getting index stats: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(setup_vector_search_index())
