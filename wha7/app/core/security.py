"""Security infrastructure for the Wha7 application.

This module provides a comprehensive security system including:
- Multiple authentication schemes (JWT, OAuth2, Azure AD)
- Role-based access control (RBAC)
- Security middleware for request/response protection
- Token management and validation
- Rate limiting and brute force protection

The security system implements industry best practices and integrates
with Azure Active Directory while maintaining support for traditional
authentication methods.
"""

from datetime import datetime, timedelta
from typing import Optional, List, Union, Dict, Any
from fastapi import Depends, HTTPException, Security, status
from fastapi.security import OAuth2PasswordBearer, SecurityScopes
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel, ValidationError
import time
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient
from fastapi_limiter import FastAPILimiter
from fastapi_limiter.depends import RateLimiter

from app.core.config import get_settings, Settings
from app.models.domain.user import UserInDB, TokenData

# Get application settings
settings = get_settings()

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# OAuth2 scheme for token extraction
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_PREFIX}/auth/token",
    scopes={
        "user": "Standard user access",
        "admin": "Administrator access",
        "moderator": "Content moderator access"
    }
)

class SecurityService:
    """Core security service implementing authentication and authorization."""
    
    def __init__(self):
        """Initialize security service with necessary clients and settings."""
        self.azure_credential = DefaultAzureCredential() if settings.AZURE.AZURE_KEY_VAULT_NAME else None
        self._setup_azure_clients()
    
    def _setup_azure_clients(self):
        """Set up Azure-specific security clients."""
        if self.azure_credential and settings.AZURE.AZURE_KEY_VAULT_NAME:
            vault_url = f"https://{settings.AZURE.AZURE_KEY_VAULT_NAME}.vault.azure.net"
            self.key_vault_client = SecretClient(
                vault_url=vault_url,
                credential=self.azure_credential
            )
    
    async def get_current_user(
        self,
        security_scopes: SecurityScopes,
        token: str = Depends(oauth2_scheme),
    ) -> UserInDB:
        """Validate token and return current user with scope verification."""
        if security_scopes.scopes:
            authenticate_value = f'Bearer scope="{security_scopes.scope_str}"'
        else:
            authenticate_value = "Bearer"
            
        credentials_exception = HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": authenticate_value},
        )
        
        try:
            # Decode JWT token
            payload = jwt.decode(
                token,
                settings.SECRET_KEY,
                algorithms=[settings.JWT_ALGORITHM]
            )
            user_id: str = payload.get("sub")
            if user_id is None:
                raise credentials_exception
                
            token_scopes = payload.get("scopes", [])
            token_data = TokenData(scopes=token_scopes, user_id=user_id)
        except (JWTError, ValidationError):
            raise credentials_exception
            
        # Get user from database
        user = await self.get_user(token_data.user_id)
        if user is None:
            raise credentials_exception
            
        # Verify scopes
        for scope in security_scopes.scopes:
            if scope not in token_data.scopes:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Not enough permissions",
                    headers={"WWW-Authenticate": authenticate_value},
                )
                
        return user
    
    def create_access_token(
        self,
        data: dict,
        expires_delta: Optional[timedelta] = None
    ) -> str:
        """Create JWT access token with optional expiration."""
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
            
        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(
            to_encode,
            settings.SECRET_KEY,
            algorithm=settings.JWT_ALGORITHM
        )
        return encoded_jwt
    
    async def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify password against hashed version."""
        return pwd_context.verify(plain_password, hashed_password)
    
    def get_password_hash(self, password: str) -> str:
        """Generate password hash."""
        return pwd_context.hash(password)

class RoleBasedAuth:
    """Role-based access control implementation."""
    
    def __init__(self):
        """Initialize RBAC with role definitions and permissions."""
        self.role_permissions = {
            "admin": {
                "user:read", "user:write", "user:delete",
                "content:read", "content:write", "content:delete",
                "settings:read", "settings:write"
            },
            "moderator": {
                "content:read", "content:write",
                "user:read"
            },
            "user": {
                "content:read",
                "user:read"
            }
        }
    
    def has_permission(self, user_role: str, required_permission: str) -> bool:
        """Check if role has specific permission."""
        return required_permission in self.role_permissions.get(user_role, set())
    
    def require_permission(self, permission: str):
        """Dependency for requiring specific permission."""
        async def permission_dependency(
            current_user: UserInDB = Security(security_service.get_current_user)
        ):
            if not self.has_permission(current_user.role, permission):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Not enough permissions"
                )
            return current_user
        return permission_dependency

class RateLimitManager:
    """Rate limiting implementation with Redis backend."""
    
    def __init__(self):
        """Initialize rate limiting with Redis connection."""
        self.enabled = settings.FEATURES.ENABLE_RATE_LIMITING
    
    async def initialize(self, redis_url: str):
        """Initialize rate limiting with Redis."""
        if self.enabled:
            await FastAPILimiter.init(redis_url)
    
    def limit(
        self,
        calls: int,
        period: int,
        key_func=None
    ):
        """Create rate limit decorator."""
        if not self.enabled:
            return lambda x: x
            
        return RateLimiter(
            times=calls,
            seconds=period,
            key_func=key_func
        )

# Initialize security components
security_service = SecurityService()
rbac = RoleBasedAuth()
rate_limiter = RateLimitManager()

# Example security dependencies
def get_current_active_user(
    current_user: UserInDB = Security(security_service.get_current_user, scopes=["user"])
) -> UserInDB:
    """Dependency for getting current active user."""
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user

def get_current_admin(
    current_user: UserInDB = Security(security_service.get_current_user, scopes=["admin"])
) -> UserInDB:
    """Dependency for getting current admin user."""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required"
        )
    return current_user

# Example usage of rate limiting
standard_rate_limit = rate_limiter.limit(
    calls=100,
    period=60,
    key_func=lambda r: r.client.host
)

# Security middleware
async def security_middleware(request, call_next):
    """Security middleware for request/response protection."""
    # Add security headers
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    
    return response