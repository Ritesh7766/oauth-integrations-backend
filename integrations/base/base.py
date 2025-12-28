from abc import ABC, abstractmethod
import json
from typing import Any

from fastapi import HTTPException, Request
from fastapi.responses import HTMLResponse

from integrations.base.integration_item import IntegrationItem
from redis_client import delete_key_redis, get_value_redis


class OAuthIntegration(ABC):
    STATE_TTL: int = 600
    CREDENTIALS_TTL: int = 600
    PREFIX: str = ""

    @abstractmethod
    async def authorize(self, user_id: str, org_id: str) -> str: ...

    @abstractmethod
    async def oauth2callback(self, request: Request) -> HTMLResponse: ...

    @abstractmethod
    async def get_items(self, credentials: str) -> list[IntegrationItem]: ...

    async def get_credentials(self, user_id: str, org_id: str) -> dict[str, Any]:
        key = f"{self.PREFIX}_credentials:{org_id}:{user_id}"

        raw = await get_value_redis(key)
        if raw is None:
            raise HTTPException(status_code=400, detail="No credentials found.")

        try:
            credentials = json.loads(raw)
        except json.JSONDecodeError:
            raise HTTPException(status_code=500, detail="Corrupted credentials data.")

        await delete_key_redis(key)
        return credentials
