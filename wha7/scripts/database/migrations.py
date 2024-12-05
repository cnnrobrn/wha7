# scripts/database/migrations.py
"""Database migration helper functions."""

import alembic.config
import os
from alembic import command

def run_migrations():
    """Run pending database migrations."""
    try:
        # Get alembic configuration
        alembic_cfg = alembic.config.Config("alembic.ini")
        
        # Run migrations
        command.upgrade(alembic_cfg, "head")
        
        print("Migrations completed successfully")
        
    except Exception as e:
        print(f"Migration failed: {str(e)}")
        raise

def create_migration(message: str):
    """Create a new migration."""
    try:
        # Get alembic configuration
        alembic_cfg = alembic.config.Config("alembic.ini")
        
        # Create migration
        command.revision(
            alembic_cfg,
            message=message,
            autogenerate=True
        )
        
        print(f"Migration created: {message}")
        
    except Exception as e:
        print(f"Migration creation failed: {str(e)}")
        raise

def rollback_migration(revision: str):
    """Rollback to a specific migration."""
    try:
        # Get alembic configuration
        alembic_cfg = alembic.config.Config("alembic.ini")
        
        # Rollback
        command.downgrade(alembic_cfg, revision)
        
        print(f"Rollback to {revision} completed")
        
    except Exception as e:
        print(f"Rollback failed: {str(e)}")
        raise