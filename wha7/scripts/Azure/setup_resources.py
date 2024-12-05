# scripts/azure/setup_resources.py
"""Azure resource setup and configuration script."""

from azure.identity import DefaultAzureCredential
from azure.mgmt.resource import ResourceManagementClient
from azure.mgmt.web import WebSiteManagementClient
from azure.mgmt.containerregistry import ContainerRegistryManagementClient
import os

def setup_azure_resources(environment: str):
    """Set up required Azure resources for the application."""
    try:
        # Initialize credentials
        credential = DefaultAzureCredential()
        subscription_id = os.getenv("AZURE_SUBSCRIPTION_ID")
        
        # Initialize clients
        resource_client = ResourceManagementClient(credential, subscription_id)
        web_client = WebSiteManagementClient(credential, subscription_id)
        acr_client = ContainerRegistryManagementClient(credential, subscription_id)
        
        # Resource group setup
        resource_group = f"wha7-{environment}-rg"
        location = "eastus"
        
        # Create resource group
        resource_client.resource_groups.create_or_update(
            resource_group,
            {"location": location}
        )
        
        # Create Container Registry
        registry_name = f"wha7{environment}registry"
        acr_client.registries.begin_create(
            resource_group,
            registry_name,
            {
                "location": location,
                "sku": {"name": "Standard"},
                "admin_user_enabled": True
            }
        ).result()
        
        # Create App Service Plan
        plan_name = f"wha7-{environment}-plan"
        web_client.app_service_plans.begin_create_or_update(
            resource_group,
            plan_name,
            {
                "location": location,
                "sku": {"name": "P1v2"},
                "kind": "linux"
            }
        ).result()
        
        # Create App Service
        app_name = f"wha7-{environment}-app"
        web_client.web_apps.begin_create_or_update(
            resource_group,
            app_name,
            {
                "location": location,
                "server_farm_id": f"/subscriptions/{subscription_id}/resourceGroups/{resource_group}/providers/Microsoft.Web/serverfarms/{plan_name}",
                "site_config": {
                    "linux_fx_version": "DOCKER",
                    "always_on": True
                }
            }
        ).result()
        
        print(f"Azure resources created successfully for {environment}")
        
    except Exception as e:
        print(f"Resource setup failed: {str(e)}")
        raise
