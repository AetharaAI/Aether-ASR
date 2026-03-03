"""Account and user state endpoints."""
from fastapi import APIRouter, Depends
from typing import Optional

from app.services.auth import resolve_entitlement, Entitlement

router = APIRouter()

@router.get("/whoami")
async def whoami(entitlement: Entitlement = Depends(resolve_entitlement)):
    """Return the current user's entitlement and tier information."""
    return {
        "authenticated": entitlement.tier != "ANON",
        "sub": entitlement.sub,
        "anon_id": entitlement.anon_id,
        "roles": entitlement.roles,
        "tier": entitlement.tier,
        "remaining_quota": entitlement.remaining_quota
    }
