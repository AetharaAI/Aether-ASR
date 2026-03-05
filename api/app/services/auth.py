"""Authentication services — open access (auth disabled)."""
import structlog

logger = structlog.get_logger()


class Entitlement:
    """Open-access entitlement stub. All features unlocked."""
    def __init__(self):
        self.tier = "OPEN"
        self.sub = "open"
        self.anon_id = None
        self.roles = ["pro_audio"]
        self.remaining_quota = -1  # unlimited

        # Legacy shims
        self.id = "open"
        self.tenant_id = "open"


async def resolve_entitlement(*args, **kwargs) -> Entitlement:
    """No-op entitlement resolver — always returns open access."""
    return Entitlement()


async def require_pro_audio(*args, **kwargs) -> Entitlement:
    """No-op — all users have pro access."""
    return Entitlement()


async def verify_api_key(*args, **kwargs) -> Entitlement:
    """No-op — no API key required."""
    return Entitlement()


async def verify_admin(*args, **kwargs) -> Entitlement:
    """No-op — no admin check required."""
    return Entitlement()
