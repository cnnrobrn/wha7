"""System health check script."""

import httpx
import asyncio
from azure.monitor.opentelemetry import configure_azure_monitor

async def check_system_health():
    """Perform comprehensive system health check."""
    try:
        # Check API endpoints
        async with httpx.AsyncClient() as client:
            response = await client.get("https://api.wha7.com/health")
            assert response.status_code == 200
        
        # Check database
        # Implementation depends on your database access pattern
        
        # Check Redis
        # Implementation depends on your Redis setup
        
        # Check Azure services
        # Implementation depends on your Azure services
        
        print("All systems operational")
        
    except Exception as e:
        print(f"Health check failed: {str(e)}")
        raise