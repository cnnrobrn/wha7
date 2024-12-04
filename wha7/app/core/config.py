"""Configuration management for the Wha7 application.

This module handles all configuration aspects of the application including:
- Environment variable loading and validation using Pydantic
- Azure App Configuration integration for dynamic settings
- Azure Key Vault integration for secrets
- Feature flag management
- Environment-specific configurations
- Application settings validation and management

The configuration system is designed to be:
1. Type-safe through Pydantic validation
2. Environment-aware (dev, staging, prod)
3. Secure with proper secret management
4. Flexible for testing and local development
5. Integrated with Azure services for cloud deployment
"""

from functools import lru_cache
from typing import List, Optional, Dict, Any
from pydantic_settings import BaseSettings, SettingsConfigDict
from azure.identity import DefaultAzureCredential
from azure.appconfiguration import AzureAppConfigurationClient
from azure.keyvault.secrets import SecretClient
import logging
from enum import Enum

# Configure logging
logger = logging.getLogger(__name__)

class EnvironmentType(str, Enum):
    """Environment types for configuration management"""
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"

class FeatureFlags(BaseSettings):
    """Feature flag configurations"""
    
    # User features
    ENABLE_SOCIAL_LOGIN: bool = False
    ENABLE_REFERRAL_SYSTEM: bool = True
    
    # Content features
    ENABLE_IMAGE_PROCESSING: bool = True
    ENABLE_VIDEO_PROCESSING: bool = False
    
    # API features
    ENABLE_RATE_LIMITING: bool = True
    ENABLE_CACHING: bool = True
    
    # Monitoring features
    ENABLE_ADVANCED_METRICS: bool = False
    ENABLE_DEBUG_LOGGING: bool = False

class DatabaseSettings(BaseSettings):
    """Database-specific configurations"""
    
    DB_DRIVER: str = "postgresql+asyncpg"
    DB_HOST: str
    DB_PORT: int
    DB_USER: str
    DB_PASSWORD: str
    DB_NAME: str
    DB_POOL_SIZE: int = 20
    DB_MAX_OVERFLOW: int = 10
    DB_POOL_TIMEOUT: int = 30
    
    @property
    def asyncpg_url(self) -> str:
        """Generate AsyncPG connection URL"""
        return (
            f"{self.DB_DRIVER}://{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )

class AzureSettings(BaseSettings):
    """Azure-specific configurations"""
    
    # Azure App Configuration
    AZURE_APP_CONFIG_ENDPOINT: Optional[str] = None
    
    # Azure Key Vault
    AZURE_KEY_VAULT_NAME: Optional[str] = None
    
    # Azure Storage
    AZURE_STORAGE_ACCOUNT: Optional[str] = None
    AZURE_STORAGE_KEY: Optional[str] = None
    
    # Azure AI Services
    AZURE_OPENAI_ENDPOINT: Optional[str] = None
    AZURE_OPENAI_KEY: Optional[str] = None

class Settings(BaseSettings):
    """Main application settings with environment-specific configurations"""
    
    # Basic application settings
    APP_NAME: str = "Wha7"
    APP_VERSION: str = "2.0.0"
    DEBUG: bool = False
    ENVIRONMENT: EnvironmentType = EnvironmentType.DEVELOPMENT
    
    # Security settings
    SECRET_KEY: str
    ALLOWED_ORIGINS: List[str] = ["*"]
    API_KEY_HEADER: str = "X-API-Key"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # Feature flags - defaults that can be overridden
    FEATURES: FeatureFlags = FeatureFlags()
    
    # Database settings
    DB: DatabaseSettings
    
    # Azure settings
    AZURE: AzureSettings
    
    # Cache settings
    REDIS_URL: Optional[str] = None
    CACHE_TTL_SECONDS: int = 3600
    
    # API settings
    API_V1_PREFIX: str = "/api/v1"
    DOCS_URL: Optional[str] = "/docs"
    OPENAPI_URL: Optional[str] = "/openapi.json"
    
    @property
    def PROD(self) -> bool:
        """Check if environment is production"""
        return self.ENVIRONMENT == EnvironmentType.PRODUCTION
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True
    )

class ConfigurationManager:
    """Manages application configuration with Azure integration"""
    
    def __init__(self, settings: Settings):
        self.settings = settings
        self._app_config_client = None
        self._key_vault_client = None
        
        # Initialize Azure clients if in cloud environment
        if settings.AZURE.AZURE_APP_CONFIG_ENDPOINT:
            self._initialize_azure_clients()
    
    def _initialize_azure_clients(self):
        """Initialize Azure service clients"""
        try:
            # Use DefaultAzureCredential for authentication
            credential = DefaultAzureCredential()
            
            # Initialize App Configuration client
            if self.settings.AZURE.AZURE_APP_CONFIG_ENDPOINT:
                self._app_config_client = AzureAppConfigurationClient(
                    self.settings.AZURE.AZURE_APP_CONFIG_ENDPOINT,
                    credential=credential
                )
            
            # Initialize Key Vault client
            if self.settings.AZURE.AZURE_KEY_VAULT_NAME:
                vault_url = f"https://{self.settings.AZURE.AZURE_KEY_VAULT_NAME}.vault.azure.net"
                self._key_vault_client = SecretClient(
                    vault_url=vault_url,
                    credential=credential
                )
        
        except Exception as e:
            logger.error(f"Failed to initialize Azure clients: {str(e)}")
            if self.settings.PROD:
                raise
    
    async def get_feature_flag(self, feature_name: str) -> bool:
        """Get feature flag value from Azure App Configuration or local settings"""
        if self._app_config_client:
            try:
                feature = await self._app_config_client.get_configuration_setting(
                    key=f".appconfig.featureflag/{feature_name}",
                    label=self.settings.ENVIRONMENT.value
                )
                return feature.value.get("enabled", False)
            except Exception as e:
                logger.error(f"Error fetching feature flag {feature_name}: {str(e)}")
        
        # Fallback to local settings
        return getattr(self.settings.FEATURES, feature_name, False)
    
    async def get_secret(self, secret_name: str) -> Optional[str]:
        """Get secret from Azure Key Vault or local settings"""
        if self._key_vault_client:
            try:
                secret = await self._key_vault_client.get_secret(secret_name)
                return secret.value
            except Exception as e:
                logger.error(f"Error fetching secret {secret_name}: {str(e)}")
        
        # Fallback to local settings
        return getattr(self.settings, secret_name, None)

@lru_cache()
def get_settings() -> Settings:
    """Get cached application settings"""
    return Settings()

@lru_cache()
def get_config_manager() -> ConfigurationManager:
    """Get cached configuration manager instance"""
    return ConfigurationManager(get_settings())

# Example usage in other parts of the application:
# settings = get_settings()
# config_manager = get_config_manager()