"""Authentication services."""
from fastapi import HTTPException, status, Header, Request, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional
import hashlib
import secrets

from app.config import settings
from app.services.database import get_api_key_by_hash


security = HTTPBearer(auto_error=False)


async def verify_api_key(
    x_api_key: Optional[str] = Header(None, alias=settings.API_KEY_HEADER)
) -> dict:
    """Verify API key from header."""
    if not x_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            headers={"WWW-Authenticate": "ApiKey"},
            detail={
                "error": {
                    "code": "MISSING_API_KEY",
                    "message": f"Missing {settings.API_KEY_HEADER} header"
                }
            }
        )
    
    # Hash the provided key
    key_hash = hashlib.sha256(x_api_key.encode()).hexdigest()
    
    # Look up in database
    api_key_obj = await get_api_key_by_hash(key_hash)
    
    if not api_key_obj:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            headers={"WWW-Authenticate": "ApiKey"},
            detail={
                "error": {
                    "code": "INVALID_API_KEY",
                    "message": "Invalid API key"
                }
            }
        )
    
    # Check if active
    if not api_key_obj.is_active or api_key_obj.is_revoked:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": {
                    "code": "REVOKED_API_KEY",
                    "message": "API key has been revoked"
                }
            }
        )
    
    # Check expiration
    if api_key_obj.expires_at and api_key_obj.expires_at < datetime.utcnow():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": {
                    "code": "EXPIRED_API_KEY",
                    "message": "API key has expired"
                }
            }
        )
    
    # Update last used
    await update_api_key_last_used(api_key_obj.id)
    
    return {
        "id": api_key_obj.id,
        "tenant_id": api_key_obj.tenant_id,
        "scopes": api_key_obj.scopes
    }


async def verify_api_key_optional(
    x_api_key: Optional[str] = Header(None, alias=settings.API_KEY_HEADER)
) -> Optional[dict]:
    """Optionally verify API key."""
    if not x_api_key:
        return None
    try:
        return await verify_api_key(x_api_key)
    except HTTPException:
        return None


async def verify_api_key_websocket(api_key: str) -> dict:
    """Verify API key for WebSocket connections."""
    return await verify_api_key(api_key)


async def verify_admin(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> dict:
    """Verify admin JWT token."""
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authorization"
        )
    
    # JWT verification would go here
    # For now, placeholder
    return {"admin": True}


from datetime import datetime
from fastapi import Depends


async def update_api_key_last_used(key_id: str):
    """Update last used timestamp for API key."""
    # This would update the database
    pass
