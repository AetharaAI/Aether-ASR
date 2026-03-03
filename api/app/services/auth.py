"""Authentication services."""
from fastapi import HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt
from jwt import PyJWKClient
import structlog
from typing import Optional

logger = structlog.get_logger()

# Passport configuration
PASSPORT_ISSUER = "https://passport.aetherpro.us/realms/aetherpro"
JWKS_URL = f"{PASSPORT_ISSUER}/protocol/openid-connect/certs"

try:
    jwks_client = PyJWKClient(JWKS_URL)
except Exception as e:
    logger.error("failed_to_initialize_jwks_client", error=str(e))
    jwks_client = None

security = HTTPBearer(auto_error=False)

def verify_token(token: str) -> dict:
    """Verify standard JWT using Passport-IAM's JWKS."""
    if not jwks_client:
        raise HTTPException(status_code=500, detail="OIDC JWKS Client not initialized.")
    try:
        signing_key = jwks_client.get_signing_key_from_jwt(token)
        data = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            issuer=PASSPORT_ISSUER,
            options={"verify_aud": False} # Accept standard audience for this realm
        )
        return data
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.PyJWTError as e:
        logger.error("jwt_verification_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    """Extract and verify the current user from the Bearer token."""
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authorization header"
        )
    user_data = verify_token(credentials.credentials)
    return user_data

async def require_pro_audio(user: dict = Depends(get_current_user)) -> dict:
    """Dependency that enforces the `pro_audio` realm role as requested by the Unified SaaS Architecture."""
    realm_access = user.get("realm_access", {})
    roles = realm_access.get("roles", [])
    if "pro_audio" not in roles:
        logger.warning("pro_audio_role_missing", user_id=user.get("sub"))
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The 'pro_audio' realm role is required for this action."
        )
    
    # We map user.sub to id and tenant_id to support legacy dependencies expecting an API Key shape
    # The ASR models depend on api_key.tenant_id to partition user data.
    return type("AuthenticatedUser", (), {
        "id": user.get("sub"),
        "tenant_id": user.get("sub"),
        "scopes": roles,
        "sub": user.get("sub"),
        "raw_token": user
    })()

# --- Legacy Compatibility Shims ---
# During transition, we map older auth methods directly to the new `require_pro_audio`.
async def verify_api_key(user=Depends(require_pro_audio)):
    return user

async def verify_api_key_optional(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)):
    if not credentials:
        return None
    try:
        user = verify_token(credentials.credentials)
        return type("AuthenticatedUser", (), {
            "id": user.get("sub"),
            "tenant_id": user.get("sub"),
            "scopes": user.get("realm_access", {}).get("roles", [])
        })()
    except Exception:
        return None

async def verify_admin(user=Depends(require_pro_audio)):
    """Temporarily maps admin to anyone with `pro_audio`, or we can check a `billing-admin` role later."""
    return user
