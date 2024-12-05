# scripts/maintenance/performance_monitor.py
"""Performance monitoring and optimization script."""

import psutil
import asyncio
from azure.monitor import MonitorClient
from datetime import datetime, timedelta

async def monitor_performance():
    """Monitor system performance metrics."""
    try:
        # System metrics
        cpu_percent = psutil.cpu_percent()
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        # Application metrics (from Azure)
        monitor_client = MonitorClient()
        metrics = await monitor_client.metrics.get(
            resource_uri="your_app_resource_uri",
            timespan=timedelta(hours=1),
            interval=timedelta(minutes=1),
            metric_names=['requests', 'response_time', 'errors']
        )
        
        # Log metrics
        print(f"CPU Usage: {cpu_percent}%")
        print(f"Memory Usage: {memory.percent}%")
        print(f"Disk Usage: {disk.percent}%")
        
        return {
            'system': {
                'cpu': cpu_percent,
                'memory': memory.percent,
                'disk': disk.percent
            },
            'application': metrics
        }
    
    except Exception as e:
        print(f"Performance monitoring failed: {str(e)}")
        raise