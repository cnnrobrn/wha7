"""Search service implementation for the Wha7 application.

This module provides a comprehensive search system with vector similarity search,
result ranking, and caching capabilities. It's designed to work with both text
and vector embeddings to find similar items and outfits.

Key features:
- Async vector database operations
- Intelligent query processing
- Configurable ranking algorithms
- Redis-based caching
- Search analytics tracking
- Performance optimization
"""

from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import asyncio
import json
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, text
from redis import asyncio as aioredis
import numpy as np
from cohere import AsyncClient as CohereClient

from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.database.outfit import Item, Link
from app.models.domain.search import (
    SearchQuery,
    SearchResult,
    SearchAnalytics
)

# Initialize components
logger = get_logger(__name__)
settings = get_settings()

class SearchService:
    """Core search service implementing vector and text-based search."""
    
    def __init__(self, cohere_client: CohereClient, redis_client: aioredis.Redis):
        """Initialize search service with necessary clients."""
        self.cohere = cohere_client
        self.redis = redis_client
        self.embed_model = settings.EMBED_MODEL
        self.embed_dimensions = settings.EMBED_DIMENSIONS
        self.cache_ttl = settings.CACHE_TTL_SECONDS
    
    async def search_items(
        self,
        query: SearchQuery,
        db: AsyncSession,
        limit: int = 10
    ) -> List[SearchResult]:
        """Search for items using vector similarity.
        
        This method:
        1. Checks cache for existing results
        2. Processes query and generates embeddings
        3. Performs vector similarity search
        4. Ranks and filters results
        5. Updates cache and analytics
        """
        try:
            # Check cache first
            cache_key = self._generate_cache_key(query)
            cached_results = await self._get_cached_results(cache_key)
            if cached_results:
                return cached_results
            
            # Generate embedding for search query
            query_embedding = await self._generate_embedding(query.text)
            
            # Perform vector search
            similar_items = await self._vector_similarity_search(
                query_embedding,
                db,
                limit=limit * 2  # Get extra results for filtering
            )
            
            # Apply filters and ranking
            filtered_results = await self._filter_and_rank_results(
                similar_items,
                query,
                db
            )
            
            # Cache results
            await self._cache_results(cache_key, filtered_results[:limit])
            
            # Track analytics asynchronously
            asyncio.create_task(
                self._track_search_analytics(query, filtered_results)
            )
            
            return filtered_results[:limit]
            
        except Exception as e:
            logger.error("Search failed", error=e, query=query.text)
            raise

    async def _generate_embedding(self, text: str) -> List[float]:
        """Generate vector embedding for text using Cohere."""
        try:
            response = await self.cohere.embed(
                texts=[text],
                model=self.embed_model,
                input_type="search_query"
            )
            return response.embeddings[0]
        except Exception as e:
            logger.error("Failed to generate embedding", error=e, text=text)
            raise

    async def _vector_similarity_search(
        self,
        query_embedding: List[float],
        db: AsyncSession,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """Perform vector similarity search in the database."""
        try:
            # Vector similarity query using dot product
            query = text("""
                WITH similarity AS (
                    SELECT 
                        i.id as item_id,
                        i.description,
                        i.search,
                        embedding <=> :embedding::vector as similarity_score
                    FROM item_embeddings ie
                    JOIN items i ON i.id = ie.item_id
                    WHERE embedding IS NOT NULL
                    ORDER BY embedding <=> :embedding::vector
                    LIMIT :limit
                )
                SELECT 
                    s.item_id,
                    s.description,
                    s.search,
                    s.similarity_score,
                    o.id as outfit_id,
                    o.image_data
                FROM similarity s
                JOIN items i ON i.id = s.item_id
                JOIN outfits o ON o.id = i.outfit_id
            """)
            
            result = await db.execute(
                query,
                {
                    "embedding": query_embedding,
                    "limit": limit
                }
            )
            
            return [dict(row) for row in result]
            
        except Exception as e:
            logger.error("Vector search failed", error=e)
            raise

    async def _filter_and_rank_results(
        self,
        items: List[Dict[str, Any]],
        query: SearchQuery,
        db: AsyncSession
    ) -> List[SearchResult]:
        """Apply filters and ranking to search results."""
        try:
            filtered_items = []
            
            for item in items:
                # Apply basic filters
                if query.min_price or query.max_price:
                    price_query = select(func.avg(Link.price)).where(
                        Link.item_id == item['item_id']
                    )
                    avg_price = await db.scalar(price_query)
                    
                    if avg_price:
                        if query.min_price and avg_price < query.min_price:
                            continue
                        if query.max_price and avg_price > query.max_price:
                            continue
                
                # Calculate ranking score
                ranking_score = await self._calculate_ranking_score(
                    item,
                    query,
                    db
                )
                
                filtered_items.append(
                    SearchResult(
                        item_id=item['item_id'],
                        outfit_id=item['outfit_id'],
                        description=item['description'],
                        similarity_score=item['similarity_score'],
                        ranking_score=ranking_score
                    )
                )
            
            # Sort by ranking score
            filtered_items.sort(key=lambda x: x.ranking_score, reverse=True)
            return filtered_items
            
        except Exception as e:
            logger.error("Filtering and ranking failed", error=e)
            raise

    async def _calculate_ranking_score(
        self,
        item: Dict[str, Any],
        query: SearchQuery,
        db: AsyncSession
    ) -> float:
        """Calculate comprehensive ranking score for an item.
        
        Considers:
        - Vector similarity score
        - Price alignment with query
        - Review ratings
        - Historical engagement
        - Freshness
        """
        try:
            # Get item metrics
            metrics_query = select(
                func.avg(Link.rating).label('avg_rating'),
                func.avg(Link.reviews_count).label('avg_reviews')
            ).where(Link.item_id == item['item_id'])
            
            result = await db.execute(metrics_query)
            metrics = result.first()
            
            # Calculate score components
            similarity_weight = 0.4
            rating_weight = 0.3
            reviews_weight = 0.2
            freshness_weight = 0.1
            
            similarity_score = 1 - item['similarity_score']  # Convert distance to similarity
            rating_score = metrics.avg_rating / 5.0 if metrics.avg_rating else 0.5
            reviews_score = min(metrics.avg_reviews / 1000, 1.0) if metrics.avg_reviews else 0.5
            
            # Calculate freshness based on item age
            freshness_score = 1.0  # Implement based on your needs
            
            # Combine scores
            final_score = (
                similarity_score * similarity_weight +
                rating_score * rating_weight +
                reviews_score * reviews_weight +
                freshness_score * freshness_weight
            )
            
            return final_score
            
        except Exception as e:
            logger.error("Ranking calculation failed", error=e)
            return 0.0

    async def _get_cached_results(
        self,
        cache_key: str
    ) -> Optional[List[SearchResult]]:
        """Retrieve cached search results."""
        try:
            cached = await self.redis.get(cache_key)
            if cached:
                return [
                    SearchResult(**item)
                    for item in json.loads(cached)
                ]
            return None
        except Exception as e:
            logger.error("Cache retrieval failed", error=e)
            return None

    async def _cache_results(
        self,
        cache_key: str,
        results: List[SearchResult]
    ):
        """Cache search results with expiration."""
        try:
            serialized = json.dumps([
                result.dict()
                for result in results
            ])
            await self.redis.setex(
                cache_key,
                self.cache_ttl,
                serialized
            )
        except Exception as e:
            logger.error("Cache update failed", error=e)

    def _generate_cache_key(self, query: SearchQuery) -> str:
        """Generate cache key for search query."""
        components = [
            query.text,
            str(query.min_price or ''),
            str(query.max_price or ''),
            query.category or ''
        ]
        return f"search:{':'.join(components)}"
    # In app/api/v1/endpoints/search.py

    @router.post("/rag_search")
    async def rag_search(
        request: Request,
        search_service: SearchService = Depends(get_search_service),
        db: AsyncSession = Depends(get_session)
    ):
        """Perform RAG search for items."""
        try:
            data = await request.json()
            description = data.get("item_description")
            
            if not description:
                raise HTTPException(status_code=400, detail="Missing item description")
                
            # Find similar items using vector search
            similar_items = await search_service.find_similar_items(
                query=description,
                limit=1
            )
            
            if not similar_items:
                raise HTTPException(status_code=404, detail="No matching items found")
                
            return {"item_id": similar_items[0].id}
        except HTTPException:
            raise
        except Exception as e:
            logger.error("RAG search failed", error=e)
            raise HTTPException(status_code=500, detail="Search failed")
        
    async def _track_search_analytics(
        self,
        query: SearchQuery,
        results: List[SearchResult]
    ):
        """Track search analytics asynchronously."""
        try:
            analytics = SearchAnalytics(
                query_text=query.text,
                timestamp=datetime.utcnow(),
                result_count=len(results),
                top_result_id=results[0].item_id if results else None,
                filters_used={
                    'min_price': query.min_price,
                    'max_price': query.max_price,
                    'category': query.category
                }
            )
            
            # Save analytics to database
            # Implementation depends on your analytics storage solution
            
        except Exception as e:
            logger.error("Analytics tracking failed", error=e)

# Initialize service with required clients
async def get_search_service() -> SearchService:
    """Get initialized search service instance."""
    cohere_client = CohereClient(api_key=settings.COHERE_API_KEY)
    redis_client = await aioredis.from_url(settings.REDIS_URL)
    return SearchService(cohere_client, redis_client)