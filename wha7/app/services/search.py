"""Cohere service for embeddings and semantic search."""

from typing import List, Optional
from cohere import AsyncClient as CohereClient
from app.core.config import get_settings
from app.core.logging import get_logger

class SearchService:
    """Search service implementing Cohere for embeddings and RAG."""
    
    def __init__(self):
        """Initialize search service with Cohere client."""
        self.client = CohereClient(api_key=settings.COHERE_API_KEY)
        self.embed_model = "embed-english-v3.0"
    
    async def generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for text using Cohere."""
        try:
            response = await self.client.embed(
                texts=texts,
                model=self.embed_model,
                input_type="search_query"
            )
            return response.embeddings
        except Exception as e:
            logger.error("Failed to generate embeddings", error=e)
            raise
            
    async def find_similar_items(
        self,
        query: str,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Find similar items using vector search."""
        try:
            # Generate embedding for search query
            query_embedding = await self.generate_embeddings([query])
            
            # Use vector similarity search in database
            # (Implementation from your existing search service)
            
        except Exception as e:
            logger.error("Similar item search failed", error=e)
            raise
