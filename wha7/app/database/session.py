
"""Database session management for the Wha7 application.

This module handles all aspects of database connection management including:
- Async SQLAlchemy session management
- Connection pooling configuration
- Transaction handling and retries
- Error recovery and logging
- Performance metrics and monitoring
- Connection lifecycle management

The implementation uses SQLAlchemy 2.0 async patterns and integrates with
Azure monitoring services.
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional, Any
from sqlalchemy.ext.asyncio import (
    create_async_engine,
    AsyncSession,
    AsyncEngine,
    async_sessionmaker
)
from sqlalchemy.pool import AsyncAdaptedQueuePool
from sqlalchemy import event
from sqlalchemy.exc import SQLAlchemyError
import time
import logging
from functools import wraps
import asyncio
from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode

from app.core.config import get_settings
from app.core.logging import get_logger

# Initialize components
logger = get_logger(__name__)
settings = get_settings()
tracer = trace.get_tracer(__name__)

class DatabaseMetrics:
    """Track database performance metrics."""
    
    def __init__(self):
        self.query_count = 0
        self.slow_queries = 0
        self.error_count = 0
        self.connection_count = 0
        self.pool_size = 0
        
        # Configure thresholds
        self.slow_query_threshold = 1.0  # seconds
    
    def record_query(self, duration: float):
        """Record query execution metrics."""
        self.query_count += 1
        if duration > self.slow_query_threshold:
            self.slow_queries += 1
    
    def record_error(self):
        """Record database error."""
        self.error_count += 1
    
    def update_pool_stats(self, engine: AsyncEngine):
        """Update connection pool statistics."""
        pool = engine.pool
        self.connection_count = pool.checkedin() + pool.checkedout()
        self.pool_size = pool.size()

class SessionManager:
    """Manage database sessions and connections."""
    
    def __init__(self):
        """Initialize session manager with configuration."""
        self.engine = self._create_engine()
        self.session_factory = self._create_session_factory()
        self.metrics = DatabaseMetrics()
        
        # Set up event listeners
        self._setup_engine_events()
    
    def _create_engine(self) -> AsyncEngine:
        """Create SQLAlchemy engine with proper configuration."""
        return create_async_engine(
            settings.DATABASE_URL,
            echo=settings.SQL_ECHO,
            pool_size=settings.DB_POOL_SIZE,
            max_overflow=settings.DB_MAX_OVERFLOW,
            pool_timeout=settings.DB_POOL_TIMEOUT,
            pool_recycle=settings.DB_POOL_RECYCLE,
            poolclass=AsyncAdaptedQueuePool,
            pool_pre_ping=True,
            # Azure driver-specific settings
            connect_args={
                "command_timeout": 60,
                "application_name": "wha7_app"
            }
        )
    
    def _create_session_factory(self) -> async_sessionmaker:
        """Create session factory with proper configuration."""
        return async_sessionmaker(
            bind=self.engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autocommit=False,
            autoflush=False
        )
    
    def _setup_engine_events(self):
        """Set up SQLAlchemy engine event listeners."""
        @event.listens_for(self.engine, 'before_cursor_execute')
        def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
            conn.info.setdefault('query_start_time', []).append(time.time())
        
        @event.listens_for(self.engine, 'after_cursor_execute')
        def after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
            start_time = conn.info['query_start_time'].pop()
            duration = time.time() - start_time
            self.metrics.record_query(duration)
            
            # Log slow queries
            if duration > self.metrics.slow_query_threshold:
                logger.warning(
                    "Slow query detected",
                    duration=duration,
                    statement=statement
                )
    
    @asynccontextmanager
    async def session(self) -> AsyncGenerator[AsyncSession, None]:
        """Get database session with automatic cleanup."""
        session: AsyncSession = self.session_factory()
        try:
            yield session
        except Exception as e:
            self.metrics.record_error()
            logger.error("Session error", error=e)
            await session.rollback()
            raise
        finally:
            await session.close()
    
    @asynccontextmanager
    async def transaction(self) -> AsyncGenerator[AsyncSession, None]:
        """Get database session with transaction management."""
        async with self.session() as session:
            transaction = await session.begin()
            try:
                yield session
                await transaction.commit()
            except Exception as e:
                await transaction.rollback()
                raise
    
    def get_metrics(self) -> dict:
        """Get current database metrics."""
        self.metrics.update_pool_stats(self.engine)
        return {
            "query_count": self.metrics.query_count,
            "slow_queries": self.metrics.slow_queries,
            "error_count": self.metrics.error_count,
            "connection_count": self.metrics.connection_count,
            "pool_size": self.metrics.pool_size
        }
    
    async def healthcheck(self) -> bool:
        """Perform database health check."""
        try:
            async with self.session() as session:
                await session.execute("SELECT 1")
            return True
        except Exception as e:
            logger.error("Database health check failed", error=e)
            return False

# Create global session manager
session_manager = SessionManager()

# Dependency for FastAPI
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency for database sessions."""
    async with session_manager.session() as session:
        yield session

def with_transaction(func):
    """Decorator for automatic transaction management."""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        async with session_manager.transaction() as session:
            return await func(*args, session=session, **kwargs)
    return wrapper

def with_tracing(func):
    """Decorator for database operation tracing."""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        with tracer.start_as_current_span(
            f"db_{func.__name__}",
            kind=trace.SpanKind.CLIENT
        ) as span:
            try:
                result = await func(*args, **kwargs)
                span.set_status(Status(StatusCode.OK))
                return result
            except Exception as e:
                span.set_status(
                    Status(StatusCode.ERROR, str(e))
                )
                raise
    return wrapper

# Example usage in repository:
"""
@with_transaction
@with_tracing
async def get_user_outfits(
    user_id: int,
    session: AsyncSession,
    limit: int = 10
) -> List[Outfit]:
    query = select(Outfit).where(
        Outfit.user_id == user_id
    ).limit(limit)
    
    result = await session.execute(query)
    return result.scalars().all()
"""