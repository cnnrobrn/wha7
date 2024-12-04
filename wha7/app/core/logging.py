"""Logging configuration and management for the Wha7 application.

This module provides a comprehensive logging system that includes:
- Structured logging with JSON formatting
- Azure Application Insights integration
- Correlation ID tracking across requests
- Performance monitoring and metrics
- Error tracking and alerting
- Custom logging utilities for consistent formatting

The logging system is designed to be:
1. Easy to use throughout the application
2. Configurable based on environment
3. Integrated with Azure monitoring
4. Capable of structured data output
5. Performance-focused with minimal overhead
"""

import logging
import json
import sys
import time
from datetime import datetime
from typing import Any, Dict, Optional
from contextvars import ContextVar
from functools import wraps
import uuid
from opencensus.ext.azure.log_exporter import AzureLogHandler
from opencensus.ext.azure.trace_exporter import AzureExporter
from opencensus.trace import config_integration
from opencensus.trace.samplers import ProbabilitySampler
from opencensus.trace.tracer import Tracer
from pythonjsonlogger import jsonlogger
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from app.core.config import get_settings

# Get application settings
settings = get_settings()

# Context variable for correlation ID
correlation_id: ContextVar[str] = ContextVar('correlation_id', default='')

class StructuredLogger:
    """Custom logger that ensures consistent structured logging."""
    
    def __init__(self, name: str):
        """Initialize structured logger with given name."""
        self.logger = logging.getLogger(name)
        self.service_name = settings.APP_NAME
        self.environment = settings.ENVIRONMENT
    
    def _build_log_dict(
        self,
        message: str,
        level: str,
        additional_fields: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Build structured log dictionary with common fields."""
        log_dict = {
            'timestamp': datetime.utcnow().isoformat(),
            'service': self.service_name,
            'environment': self.environment,
            'level': level,
            'message': message,
            'correlation_id': correlation_id.get(),
        }
        
        if additional_fields:
            log_dict.update(additional_fields)
            
        return log_dict
    
    def info(self, message: str, **kwargs):
        """Log info level message with structured data."""
        self.logger.info(
            json.dumps(self._build_log_dict(message, 'INFO', kwargs))
        )
    
    def error(self, message: str, error: Optional[Exception] = None, **kwargs):
        """Log error level message with structured data and optional exception."""
        log_dict = self._build_log_dict(message, 'ERROR', kwargs)
        
        if error:
            log_dict.update({
                'error_type': error.__class__.__name__,
                'error_message': str(error),
                'error_trace': self._get_traceback(error)
            })
            
        self.logger.error(json.dumps(log_dict))
    
    def warning(self, message: str, **kwargs):
        """Log warning level message with structured data."""
        self.logger.warning(
            json.dumps(self._build_log_dict(message, 'WARNING', kwargs))
        )
    
    def debug(self, message: str, **kwargs):
        """Log debug level message with structured data."""
        self.logger.debug(
            json.dumps(self._build_log_dict(message, 'DEBUG', kwargs))
        )
    
    @staticmethod
    def _get_traceback(error: Exception) -> str:
        """Get formatted traceback from exception."""
        import traceback
        return ''.join(traceback.format_exception(
            type(error),
            error,
            error.__traceback__
        ))

class CorrelationMiddleware(BaseHTTPMiddleware):
    """Middleware to handle correlation ID for request tracking."""
    
    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint
    ) -> Response:
        """Process request with correlation ID tracking."""
        # Get or generate correlation ID
        correlation_id.set(
            request.headers.get('X-Correlation-ID', str(uuid.uuid4()))
        )
        
        # Process request
        try:
            response = await call_next(request)
            # Add correlation ID to response headers
            response.headers['X-Correlation-ID'] = correlation_id.get()
            return response
        except Exception as e:
            # Log error with correlation ID
            logger = get_logger(__name__)
            logger.error(
                "Request processing failed",
                error=e,
                path=request.url.path,
                method=request.method
            )
            raise
        finally:
            # Reset correlation ID
            correlation_id.set('')

class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware for logging request and response details."""
    
    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint
    ) -> Response:
        """Log request and response details."""
        logger = get_logger(__name__)
        start_time = time.time()
        
        # Log request
        logger.info(
            "Request started",
            method=request.method,
            path=request.url.path,
            query_params=dict(request.query_params),
            client_host=request.client.host if request.client else None
        )
        
        try:
            response = await call_next(request)
            
            # Log response
            process_time = (time.time() - start_time) * 1000
            logger.info(
                "Request completed",
                method=request.method,
                path=request.url.path,
                status_code=response.status_code,
                process_time_ms=round(process_time, 2)
            )
            
            return response
        except Exception as e:
            process_time = (time.time() - start_time) * 1000
            logger.error(
                "Request failed",
                error=e,
                method=request.method,
                path=request.url.path,
                process_time_ms=round(process_time, 2)
            )
            raise

def setup_logging():
    """Configure logging for the application."""
    # Create JSON formatter
    class CustomJsonFormatter(jsonlogger.JsonFormatter):
        def add_fields(self, log_record, record, message_dict):
            super().add_fields(log_record, record, message_dict)
            log_record['timestamp'] = record.created
            log_record['level'] = record.levelname

    # Base configuration
    logging.basicConfig(
        level=logging.DEBUG if settings.DEBUG else logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Configure JSON handler
    json_handler = logging.StreamHandler()
    json_handler.setFormatter(CustomJsonFormatter())
    
    # Configure Azure Application Insights if available
    if settings.AZURE.AZURE_APP_CONFIG_ENDPOINT:
        # Initialize Azure monitoring
        config_integration.trace_integrations(['logging'])
        azure_handler = AzureLogHandler(
            connection_string=settings.AZURE.AZURE_APP_CONFIG_ENDPOINT
        )
        azure_handler.setFormatter(CustomJsonFormatter())
        
        # Create tracer for distributed tracing
        tracer = Tracer(
            exporter=AzureExporter(
                connection_string=settings.AZURE.AZURE_APP_CONFIG_ENDPOINT
            ),
            sampler=ProbabilitySampler(1.0)
        )
        
        # Add Azure handler
        logging.getLogger().addHandler(azure_handler)

    # Add JSON handler
    logging.getLogger().addHandler(json_handler)

def get_logger(name: str) -> StructuredLogger:
    """Get a structured logger instance."""
    return StructuredLogger(name)

# Performance monitoring decorator
def monitor_performance(name: str = None):
    """Decorator for monitoring function performance."""
    def decorator(func):
        @wraps(func)
        async def wrapped(*args, **kwargs):
            logger = get_logger(__name__)
            start_time = time.time()
            
            try:
                result = await func(*args, **kwargs)
                process_time = (time.time() - start_time) * 1000
                
                logger.info(
                    f"Function {name or func.__name__} completed",
                    process_time_ms=round(process_time, 2)
                )
                
                return result
            except Exception as e:
                process_time = (time.time() - start_time) * 1000
                logger.error(
                    f"Function {name or func.__name__} failed",
                    error=e,
                    process_time_ms=round(process_time, 2)
                )
                raise
        
        return wrapped
    return decorator

# Example usage in FastAPI endpoints:
"""
from app.core.logging import get_logger, monitor_performance

logger = get_logger(__name__)

@router.get("/items")
@monitor_performance("get_items")
async def get_items():
    logger.info("Fetching items", additional_field="value")
    try:
        items = await fetch_items()
        logger.info("Items fetched successfully", count=len(items))
        return items
    except Exception as e:
        logger.error("Failed to fetch items", error=e)
        raise
"""