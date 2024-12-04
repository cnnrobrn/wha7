"""Main FastAPI application entry point.

This module serves as the primary entry point for the Wha7 application.
It handles all core application setup including:
- FastAPI application initialization and configuration
- Middleware setup for CORS, logging, and error handling
- Database connection management
- Route registration and API versioning
- Application startup/shutdown event handlers
- Health check endpoints
- OpenAPI/Swagger documentation configuration
"""

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from sqlalchemy.ext.asyncio import AsyncSession
import time
import logging
from contextlib import asynccontextmanager

# Internal imports
from app.core.config import get_settings
from app.core.logging import setup_logging
from app.database.session import init_db, get_session
from app.api.v1.router import api_router
from app.core.exceptions import AppException
from app.core.middleware import (
    RequestLoggingMiddleware,
    ResponseTimeMiddleware
)

# Configure logging
logger = logging.getLogger(__name__)
settings = get_settings()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Handle application startup and shutdown events.
    This context manager ensures proper resource management.
    """
    # Startup
    logger.info("Starting up application...")
    try:
        # Initialize database
        await init_db()
        logger.info("Database initialized successfully")
        
        # Additional startup tasks (e.g., initialize AI clients, cache, etc.)
        # await initialize_ai_services()
        # await initialize_cache()
        
        yield  # Application runs here
        
    except Exception as e:
        logger.error(f"Startup failed: {str(e)}")
        raise
    
    # Shutdown
    finally:
        logger.info("Shutting down application...")
        # Cleanup tasks here
        # await cleanup_connections()
        logger.info("Cleanup completed")

def create_application() -> FastAPI:
    """
    Create and configure the FastAPI application instance.
    Handles all application setup including middleware, routes, and error handlers.
    """
    # Initialize FastAPI with custom configurations
    app = FastAPI(
        title="Wha7 API",
        description="Fashion discovery and social shopping platform",
        version="2.0.0",
        lifespan=lifespan,
        docs_url="/api/docs" if not settings.PROD else None,
        redoc_url="/api/redoc" if not settings.PROD else None,
    )
    
    # Configure CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Add custom middleware
    app.add_middleware(ResponseTimeMiddleware)
    app.add_middleware(RequestLoggingMiddleware)
    
    # Register exception handlers
    @app.exception_handler(AppException)
    async def app_exception_handler(request: Request, exc: AppException):
        """Handle custom application exceptions"""
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": exc.detail}
        )
    
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        """Handle request validation errors with clear messages"""
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"detail": exc.errors()}
        )
    
    # Register routers
    app.include_router(
        api_router,
        prefix="/api/v1"
    )
    
    # Health check endpoint
    @app.get("/health", tags=["Health"])
    async def health_check():
        """
        Health check endpoint for monitoring systems.
        Checks critical service dependencies.
        """
        try:
            # Get database session
            async with get_session() as session:
                # Simple query to check database connection
                await session.execute("SELECT 1")
            
            return {
                "status": "healthy",
                "timestamp": time.time(),
                "version": app.version,
                "services": {
                    "database": "connected",
                    # Add other service checks here
                    # "cache": await check_cache(),
                    # "ai_service": await check_ai_service()
                }
            }
        except Exception as e:
            logger.error(f"Health check failed: {str(e)}")
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content={
                    "status": "unhealthy",
                    "error": str(e)
                }
            )
    
    return app

# Create the application instance
app = create_application()

# Only run the server directly in development
if __name__ == "__main__":
    import uvicorn
    
    # Setup logging for development
    setup_logging()
    
    # Run the application with hot reload in development
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=not settings.PROD,
        log_level="debug" if not settings.PROD else "info"
    )