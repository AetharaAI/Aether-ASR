"""Passport-IAM Admin API integration service."""
import httpx
import structlog
from app.config import settings

logger = structlog.get_logger()

class PassportAdminClient:
    def __init__(self):
        self.base_url = settings.PASSPORT_ADMIN_URL
        self.client_id = settings.PASSPORT_CLIENT_ID
        self.client_secret = settings.PASSPORT_CLIENT_SECRET
        self.token_url = f"{self.base_url.replace('/admin', '')}/protocol/openid-connect/token"
        
    async def _get_admin_token(self) -> str:
        """Fetch an admin access token using client credentials."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.token_url,
                data={
                    "grant_type": "client_credentials",
                    "client_id": self.client_id,
                    "client_secret": self.client_secret
                }
            )
            response.raise_for_status()
            return response.json()["access_token"]
            
    async def _get_role_representation(self, role_name: str, token: str) -> dict:
        """Fetch the exact Keycloak role representation required for mapping."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/roles/{role_name}",
                headers={"Authorization": f"Bearer {token}"}
            )
            response.raise_for_status()
            return response.json()

    async def assign_realm_role(self, user_id: str, role_name: str) -> bool:
        """Assign a realm role to a user."""
        try:
            token = await self._get_admin_token()
            role = await self._get_role_representation(role_name, token)
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/users/{user_id}/role-mappings/realm",
                    headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                    json=[role]
                )
                response.raise_for_status()
                logger.info("assigned_realm_role", user_id=user_id, role=role_name)
                return True
        except Exception as e:
            logger.error("failed_to_assign_realm_role", user_id=user_id, role=role_name, error=str(e))
            return False

    async def remove_realm_role(self, user_id: str, role_name: str) -> bool:
        """Remove a realm role from a user."""
        try:
            token = await self._get_admin_token()
            role = await self._get_role_representation(role_name, token)
            
            async with httpx.AsyncClient() as client:
                # Keycloak uses DELETE with a body to remove roles
                request = httpx.Request(
                    "DELETE",
                    f"{self.base_url}/users/{user_id}/role-mappings/realm",
                    headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                    json=[role]
                )
                response = await client.send(request)
                response.raise_for_status()
                logger.info("removed_realm_role", user_id=user_id, role=role_name)
                return True
        except Exception as e:
            logger.error("failed_to_remove_realm_role", user_id=user_id, role=role_name, error=str(e))
            return False

passport_admin = PassportAdminClient()
