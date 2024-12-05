"""
Data access layer implementation. Provides:
- CRUD operations
- Custom queries
- Data aggregation
- Cache integration
- Transaction management
- Query optimization
"""
"""Base repository implementation for database operations.

This module provides a generic repository pattern implementation with common
database operations that can be inherited by specific repositories.

Features:
- Generic CRUD operations
- Type-safe queries
- Transaction management
- Common filters and operations
"""

from typing import Generic, TypeVar, Type, Optional, List, Any, Dict, Union
from sqlalchemy import select, update, delete, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Select
from datetime import datetime

from app.models.database.base import Base
from app.core.logging import get_logger

# Type variable for models
ModelType = TypeVar("ModelType", bound=Base)
logger = get_logger(__name__)

class BaseRepository(Generic[ModelType]):
    """Base repository providing common database operations."""
    
    def __init__(self, model: Type[ModelType], session: AsyncSession):
        """Initialize repository with model and session.
        
        Args:
            model: SQLAlchemy model class
            session: AsyncSession instance
        """
        self.model = model
        self.session = session
    
    async def create(self, **kwargs) -> ModelType:
        """Create a new record.
        
        Args:
            **kwargs: Model field values
            
        Returns:
            Created model instance
        """
        try:
            instance = self.model(**kwargs)
            self.session.add(instance)
            await self.session.flush()
            return instance
        except Exception as e:
            logger.error(f"Create failed for {self.model.__name__}", error=str(e))
            raise
    
    async def get(self, id: Any) -> Optional[ModelType]:
        """Get record by ID.
        
        Args:
            id: Record ID
            
        Returns:
            Model instance if found, None otherwise
        """
        try:
            query = select(self.model).where(self.model.id == id)
            result = await self.session.execute(query)
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Get failed for {self.model.__name__}", error=str(e))
            raise
    
    async def get_multi(
        self,
        *,
        skip: int = 0,
        limit: int = 100,
        filters: Optional[Dict[str, Any]] = None,
        order_by: Optional[List[Union[str, tuple]]] = None
    ) -> List[ModelType]:
        """Get multiple records with filtering and pagination.
        
        Args:
            skip: Number of records to skip
            limit: Maximum number of records to return
            filters: Dictionary of field filters
            order_by: List of fields to order by
            
        Returns:
            List of model instances
        """
        try:
            query = select(self.model)
            
            # Apply filters
            if filters:
                conditions = []
                for field, value in filters.items():
                    if isinstance(value, (list, tuple)):
                        conditions.append(getattr(self.model, field).in_(value))
                    else:
                        conditions.append(getattr(self.model, field) == value)
                query = query.where(and_(*conditions))
            
            # Apply ordering
            if order_by:
                for field in order_by:
                    if isinstance(field, tuple):
                        field_name, direction = field
                        query = query.order_by(
                            getattr(getattr(self.model, field_name), direction)()
                        )
                    else:
                        query = query.order_by(getattr(self.model, field))
            
            # Apply pagination
            query = query.offset(skip).limit(limit)
            
            result = await self.session.execute(query)
            return result.scalars().all()
        except Exception as e:
            logger.error(f"Get multi failed for {self.model.__name__}", error=str(e))
            raise
    
    async def update(
        self,
        id: Any,
        **kwargs
    ) -> Optional[ModelType]:
        """Update a record by ID.
        
        Args:
            id: Record ID
            **kwargs: Fields to update
            
        Returns:
            Updated model instance
        """
        try:
            query = (
                update(self.model)
                .where(self.model.id == id)
                .values(**kwargs)
                .returning(self.model)
            )
            result = await self.session.execute(query)
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Update failed for {self.model.__name__}", error=str(e))
            raise
    
    async def delete(self, id: Any) -> bool:
        """Delete a record by ID.
        
        Args:
            id: Record ID
            
        Returns:
            True if record was deleted, False otherwise
        """
        try:
            query = delete(self.model).where(self.model.id == id)
            result = await self.session.execute(query)
            return result.rowcount > 0
        except Exception as e:
            logger.error(f"Delete failed for {self.model.__name__}", error=str(e))
            raise
    
    async def exists(self, **kwargs) -> bool:
        """Check if record exists with given criteria.
        
        Args:
            **kwargs: Field criteria
            
        Returns:
            True if record exists, False otherwise
        """
        try:
            query = select(self.model).filter_by(**kwargs)
            result = await self.session.execute(query)
            return result.first() is not None
        except Exception as e:
            logger.error(f"Exists check failed for {self.model.__name__}", error=str(e))
            raise
    
    async def count(self, filters: Optional[Dict[str, Any]] = None) -> int:
        """Get count of records matching filters.
        
        Args:
            filters: Optional filter criteria
            
        Returns:
            Count of matching records
        """
        try:
            query = select(func.count()).select_from(self.model)
            if filters:
                query = query.filter_by(**filters)
            result = await self.session.execute(query)
            return result.scalar_one()
        except Exception as e:
            logger.error(f"Count failed for {self.model.__name__}", error=str(e))
            raise
    
    def filter(self, query: Select, filters: Dict[str, Any]) -> Select:
        """Apply filters to query.
        
        Args:
            query: Base query to filter
            filters: Filter criteria
            
        Returns:
            Filtered query
        """
        for field, value in filters.items():
            if value is not None:
                query = query.where(getattr(self.model, field) == value)
        return query