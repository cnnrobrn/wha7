# app/models/domain/common.py
from enum import Enum

class SortOrder(str, Enum):
    """Common sort order options."""
    ASC = "asc"
    DESC = "desc"

class PaginationParams(BaseModel):
    """Common pagination parameters."""
    skip: int = Field(default=0, ge=0)
    limit: int = Field(default=10, ge=1, le=100)
    sort_by: Optional[str] = None
    sort_order: SortOrder = SortOrder.DESC

class PagedResponse(BaseModel):
    """Generic paged response wrapper."""
    items: List[Any]
    total: int
    has_more: bool