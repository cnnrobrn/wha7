# scripts/azure/deploy.py
"""Azure deployment script for the Wha7 application."""

import os
import argparse
import subprocess
from azure.identity import DefaultAzureCredential
from azure.mgmt.web import WebSiteManagementClient
from azure.mgmt.containerregistry import ContainerRegistryManagementClient

def deploy_to_azure(environment: str):
    """Deploy application to Azure App Service."""
    try:
        # Load credentials
        credential = DefaultAzureCredential()
        subscription_id = os.getenv("AZURE_SUBSCRIPTION_ID")
        
        # Get clients
        web_client = WebSiteManagementClient(credential, subscription_id)
        acr_client = ContainerRegistryManagementClient(credential, subscription_id)
        
        # Build and push Docker image
        registry_name = os.getenv("AZURE_REGISTRY_NAME")
        image_name = f"{registry_name}.azurecr.io/wha7app:{environment}"
        
        subprocess.run(["docker", "build", "-t", image_name, "."])
        subprocess.run(["docker", "push", image_name])
        
        # Update App Service
        resource_group = os.getenv("AZURE_RESOURCE_GROUP")
        app_name = f"wha7app-{environment}"
        
        web_client.web_apps.create_or_update(
            resource_group,
            app_name,
            {
                "location": "eastus",
                "properties": {
                    "siteConfig": {
                        "linuxFxVersion": f"DOCKER|{image_name}",
                        "alwaysOn": True,
                        "http20Enabled": True,
                        "minTlsVersion": "1.2",
                        "healthCheckPath": "/health"
                    }
                }
            }
        )
        
        print(f"Deployment to {environment} completed successfully")
        
    except Exception as e:
        print(f"Deployment failed: {str(e)}")
        raise

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--env", choices=["dev", "staging", "prod"])
    args = parser.parse_args()
    deploy_to_azure(args.env)

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

# scripts/maintenance/health_check.py
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

# scripts/utils/env_setup.py
"""Environment setup utility."""

import os
from azure.keyvault.secrets import SecretClient
from azure.identity import DefaultAzureCredential

def setup_environment():
    """Set up environment variables from Azure Key Vault."""
    try:
        # Get Azure credentials
        credential = DefaultAzureCredential()
        
        # Get Key Vault client
        vault_url = f"https://{os.getenv('AZURE_KEY_VAULT_NAME')}.vault.azure.net"
        client = SecretClient(vault_url=vault_url, credential=credential)
        
        # Required secrets
        required_secrets = [
            "DATABASE-URL",
            "OPENAI-API-KEY",
            "COHERE-API-KEY",
            "TWILIO-ACCOUNT-SID",
            "TWILIO-AUTH-TOKEN",
            "INSTAGRAM-ACCESS-TOKEN"
        ]
        
        # Get and set secrets
        for secret_name in required_secrets:
            secret = client.get_secret(secret_name)
            os.environ[secret_name.replace("-", "_")] = secret.value
        
        print("Environment setup completed")
        
    except Exception as e:
        print(f"Environment setup failed: {str(e)}")
        raise