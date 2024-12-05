# scripts/database/cleanup.py
"""Database cleanup and maintenance operations."""

from sqlalchemy import text
from app.database.session import get_session
from datetime import datetime, timedelta

async def cleanup_database():
    """Perform database cleanup operations."""
    try:
        async with get_session() as session:
            # Clean old logs
            await session.execute(
                text("DELETE FROM logs WHERE timestamp < :cutoff"),
                {"cutoff": datetime.now() - timedelta(days=30)}
            )
            
            # Clean unused links
            await session.execute(
                text("""
                    DELETE FROM links 
                    WHERE created_at < :cutoff 
                    AND NOT EXISTS (
                        SELECT 1 FROM items 
                        WHERE items.id = links.item_id
                    )
                """),
                {"cutoff": datetime.now() - timedelta(days=7)}
            )
            
            # Vacuum analyze
            await session.execute(text("VACUUM ANALYZE"))
            
            await session.commit()
            
    except Exception as e:
        print(f"Database cleanup failed: {str(e)}")
        raise