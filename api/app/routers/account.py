"""Account and user state endpoints."""
from fastapi import APIRouter

router = APIRouter()

@router.get("/whoami")
async def whoami():
    """Return open-access status — no auth required."""
    return {
        "authenticated": False,
        "sub": None,
        "anon_id": None,
        "roles": ["pro_audio"],
        "tier": "OPEN",
        "remaining_quota": -1
    }
