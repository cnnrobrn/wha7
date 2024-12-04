"""Fashion consultant service combining OpenAI and Cohere capabilities."""

class FashionConsultantService:
    """Service that combines AI capabilities for fashion recommendations."""
    
    def __init__(
        self,
        ai_service: AIService,
        search_service: SearchService
    ):
        self.ai_service = ai_service
        self.search_service = search_service
    
    async def get_outfit_recommendations(
        self,
        image_data: Optional[str],
        text_query: Optional[str]
    ) -> List[Dict[str, Any]]:
        """Generate outfit recommendations using both AI services.
        
        Process:
        1. Use OpenAI to analyze image and/or text input
        2. Generate search queries from analysis
        3. Use Cohere to find similar items in database
        4. Combine and rank recommendations
        """
        try:
            # Get visual analysis if image provided
            if image_data:
                analysis = await self.ai_service.analyze_outfit_image(
                    image_data,
                    text_query
                )
                search_queries = self._extract_search_queries(analysis)
            else:
                search_queries = [text_query]
            
            # Find similar items using Cohere
            recommendations = []
            for query in search_queries:
                similar_items = await self.search_service.find_similar_items(
                    query
                )
                recommendations.extend(similar_items)
            
            # Rank and deduplicate recommendations
            return self._rank_recommendations(recommendations)
            
        except Exception as e:
            logger.error("Recommendation generation failed", error=e)
            raise