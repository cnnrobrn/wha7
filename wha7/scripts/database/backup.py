# scripts/database/backup.py
"""Database backup script for PostgreSQL."""

import os
import datetime
from azure.storage.blob import BlobServiceClient
import subprocess

def backup_database():
    """Create and upload database backup."""
    try:
        # Create backup
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = f"backup_{timestamp}.sql"
        
        subprocess.run([
            "pg_dump",
            "-h", os.getenv("DB_HOST"),
            "-U", os.getenv("DB_USER"),
            "-d", os.getenv("DB_NAME"),
            "-f", backup_file
        ])
        
        # Upload to Azure Storage
        blob_service = BlobServiceClient.from_connection_string(
            os.getenv("AZURE_STORAGE_CONNECTION_STRING")
        )
        container_name = "database-backups"
        
        blob_client = blob_service.get_blob_client(
            container=container_name,
            blob=backup_file
        )
        
        with open(backup_file, "rb") as data:
            blob_client.upload_blob(data)
        
        # Cleanup local file
        os.remove(backup_file)
        
        print(f"Backup completed: {backup_file}")
        
    except Exception as e:
        print(f"Backup failed: {str(e)}")
        raise