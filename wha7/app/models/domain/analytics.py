# app/models/domain/analytics.py
class ItemAnalytics(BaseModel):
    """Analytics data for items."""
    total_views: int
    total_clicks: int
    conversion_rate: float
    average_price: Optional[float]
    price_history: List[PricePoint]

class OutfitAnalytics(BaseModel):
    """Analytics data for outfits."""
    total_outfits: int
    total_items: int
    average_items_per_outfit: float
    popular_categories: List[Dict[str, int]]
    engagement_metrics: Dict[str, float]