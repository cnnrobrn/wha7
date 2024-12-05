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

# Standard library imports
import time
import logging
from contextlib import asynccontextmanager

# FastAPI imports
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from sqlalchemy.ext.asyncio import AsyncSession

# Internal imports
from app.core.config import get_settings
from app.core.logging import setup_logging
from app.database.session import init_db, get_session
from app.api.v1.router import api_router
from app.core.exceptions import AppException
from app.core.middleware import (
    RequestLoggingMiddleware,
    ResponseTimeMiddleware,
    RateLimitMiddleware
)

# Service imports
from app.services.ai_processing import AIService
from app.services.search import SearchService
from app.services.image_processing import ImageProcessingService
from app.services.social_media import SocialMediaService
from app.services.messaging import MessageService

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
        
        # Initialize services
        app.state.ai_service = await AIService()
        app.state.search_service = await SearchService()
        app.state.image_service = await ImageProcessingService()
        app.state.social_service = await SocialMediaService()
        app.state.message_service = await MessageService()
        logger.info("Services initialized successfully")
        
        yield  # Application runs here
        
    except Exception as e:
        logger.error(f"Startup failed: {str(e)}")
        raise
    
    finally:
        logger.info("Shutting down application...")
        # Cleanup services
        await app.state.ai_service.close()
        await app.state.search_service.close()
        await app.state.image_service.close()
        await app.state.social_service.close()
        await app.state.message_service.close()
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
    app.add_middleware(RateLimitMiddleware)
    
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
            # Check database connection
            async with get_session() as session:
                await session.execute("SELECT 1")
            
            # Check service statuses
            services_status = {
                "database": "connected",
                "ai_service": app.state.ai_service.status if hasattr(app.state, 'ai_service') else "not_initialized",
                "search_service": app.state.search_service.status if hasattr(app.state, 'search_service') else "not_initialized",
                "image_service": app.state.image_service.status if hasattr(app.state, 'image_service') else "not_initialized",
                "social_service": app.state.social_service.status if hasattr(app.state, 'social_service') else "not_initialized",
                "message_service": app.state.message_service.status if hasattr(app.state, 'message_service') else "not_initialized"
            }
            
            return {
                "status": "healthy",
                "timestamp": time.time(),
                "version": app.version,
                "services": services_status
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