"""Authentication services."""
from fastapi import HTTPException, status, Depends, Request, Response
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt
from jwt import PyJWKClient
import structlog
from typing import Optional
from datetime import datetime
import uuid

from app.config import settings
from app.services.cache import get_redis_client

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

# Entitlement Structures
class Entitlement:
    def __init__(self, tier: str, sub: str = None, anon_id: str = None, roles: list = None, remaining_quota: int = -1):
        self.tier = tier # "ANON", "FREE", "PRO"
        self.sub = sub
        self.anon_id = anon_id
        self.roles = roles or []
        self.remaining_quota = remaining_quota
        
        # Legacy shims
        self.id = sub or anon_id
        self.tenant_id = sub or anon_id

async def resolve_entitlement(request: Request, response: Response) -> Entitlement:
    """Dependency that extracts user state and enforces tiered limits in Redis."""
    auth_header = request.headers.get("Authorization")
    user_data = None
    if auth_header and auth_header.startswith("Bearer "):
        try:
            token = auth_header.split(" ")[1]
            user_data = verify_token(token)
        except Exception as e:
            logger.warning("invalid_token_fallback_to_anon", error=str(e))
            
    client = await get_redis_client()
            
    if user_data:
        sub = user_data.get("sub")
        roles = user_data.get("realm_access", {}).get("roles", [])
        
        if "pro_audio" in roles:
            logger.info("entitlement_resolved", tier="PRO", sub=sub)
            return Entitlement(tier="PRO", sub=sub, roles=roles, remaining_quota=-1) # -1 is unlimited
        else:
            # TIER B: FREE (10/day)
            today = datetime.utcnow().strftime("%Y%m%d")
            key = f"asr:free:{sub}:{today}"
            
            # Use basic get/incr; in prod pipelines we would use lua scripts or increment on success.
            # Assuming successful API calls.
            current = await client.get(key)
            current_int = int(current) if current else 0
            
            if current_int >= 10:
                logger.info("rate_limit_exceeded_free", sub=sub)
                raise HTTPException(status_code=429, detail="Free tier limit of 10 transcriptions per day reached. Upgrade to Pro.")
                
            await client.incr(key)
            if not current:
                await client.expire(key, 86400) # 24 hours TTL
                
            logger.info("entitlement_resolved", tier="FREE", sub=sub, remaining_quota=10 - current_int - 1)
            return Entitlement(tier="FREE", sub=sub, roles=roles, remaining_quota=10 - current_int - 1)
            
    else:
        # TIER A: ANON (2 total)
        anon_id = request.cookies.get("anon_id")
        if not anon_id:
            anon_id = str(uuid.uuid4())
            response.set_cookie(key="anon_id", value=anon_id, max_age=315360000, httponly=True, samesite="lax")
            
        key = f"asr:anon:{anon_id}:count"
        current = await client.get(key)
        current_int = int(current) if current else 0
        
        if current_int >= 2:
            logger.info("rate_limit_exceeded_anon", anon_id=anon_id)
            raise HTTPException(status_code=401, detail="Anonymous limit of 2 transcriptions reached. Please sign in to continue.")
            
        await client.incr(key)
        
        logger.info("entitlement_resolved", tier="ANON", anon_id=anon_id, remaining_quota=2 - current_int - 1)
        return Entitlement(tier="ANON", anon_id=anon_id, remaining_quota=2 - current_int - 1)

# Utility for routes that strictly require the Pro role
async def require_pro_audio(entitlement: Entitlement = Depends(resolve_entitlement)) -> Entitlement:
    if entitlement.tier != "PRO":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The 'pro_audio' realm role is required for this action."
        )
    return entitlement

# Legacy compatibility shims
async def verify_api_key(entitlement: Entitlement = Depends(resolve_entitlement)):
    return entitlement

async def verify_admin(entitlement: Entitlement = Depends(require_pro_audio)):
    return entitlement
