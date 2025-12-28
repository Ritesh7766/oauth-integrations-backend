# hubspot.py

import asyncio
import base64
import json
import secrets
from urllib.parse import urlencode

from fastapi import HTTPException, Request
from fastapi.responses import HTMLResponse
import httpx
import requests

from integrations.base import IntegrationItem, OAuthIntegration
from redis_client import add_key_value_redis, delete_key_redis, get_value_redis
from settings import hubspot_settings


class HubSpotIntegration(OAuthIntegration):
    PREFIX = "hubspot"

    async def authorize(self, user_id: str, org_id: str) -> str:
        state_data = {
            "state": secrets.token_urlsafe(32),
            "user_id": user_id,
            "org_id": org_id,
        }
        jsonified_state = json.dumps(state_data).encode("utf-8")
        encoded_state = base64.urlsafe_b64encode(jsonified_state).decode("utf-8")
        scope = "oauth " "crm.objects.companies.read"
        params = {
            "state": encoded_state,
            "scope": scope,
            "redirect_uri": hubspot_settings.redirect_uri,
        }
        auth_url = hubspot_settings.auth_url + urlencode(params)
        await add_key_value_redis(
            f"{self.PREFIX}_state:{org_id}:{user_id}",
            jsonified_state,
            expire=self.STATE_TTL,
        )
        return auth_url

    async def oauth2callback(self, request: Request) -> HTMLResponse:
        if request.query_params.get("error"):
            raise HTTPException(
                status_code=400, detail=request.query_params.get("error_description")
            )

        code = request.query_params.get("code")
        encoded_state = request.query_params.get("state")
        state_data = json.loads(base64.urlsafe_b64decode(encoded_state).decode("utf-8"))

        original_state, user_id, org_id = (
            state_data.get("state"),
            state_data.get("user_id"),
            state_data.get("org_id"),
        )
        saved_state = await get_value_redis(f"{self.PREFIX}_state:{org_id}:{user_id}")

        if not saved_state or original_state != json.loads(saved_state).get("state"):
            raise HTTPException(status_code=400, detail="State does not match.")

        async with httpx.AsyncClient() as client:
            response, _ = await asyncio.gather(
                client.post(
                    "https://api.hubspot.com/oauth/v1/token",
                    data={
                        "grant_type": "authorization_code",
                        "code": code,
                        "redirect_uri": hubspot_settings.redirect_uri,
                        "client_id": hubspot_settings.client_id,
                        "client_secret": hubspot_settings.client_secret,
                    },
                    headers={
                        "Content-Type": "application/x-www-form-urlencoded",
                    },
                ),
                delete_key_redis(f"{self.PREFIX}_state:{org_id}:{user_id}"),
            )

        await add_key_value_redis(
            f"{self.PREFIX}_credentials:{org_id}:{user_id}",
            json.dumps(response.json()),
            expire=self.CREDENTIALS_TTL,
        )

        return HTMLResponse(
            content="""
            <html>
                <script>window.close();</script>
            </html>
            """
        )

    async def get_items(self, credentials: str) -> list[IntegrationItem]:
        parsed_credentials = json.loads(
            credentials.encode("utf-8").decode("unicode_escape")
        )
        response = requests.get(
            "https://api.hubspot.com/crm/v3/objects/companies",
            headers={
                "Authorization": f'Bearer {parsed_credentials.get("access_token")}',
            },
        )
        response.raise_for_status()
        results = response.json().get("results", [])

        list_of_integration_item_metadata = []
        for result in results:
            list_of_integration_item_metadata.append(
                IntegrationItem(
                    id=result.get("id"),
                    url=result.get("url"),
                    creation_time=result.get("createdAt"),
                    last_modified_time=result.get("updatedAt"),
                    name=result.get("properties", {}).get("name"),
                )
            )

        return list_of_integration_item_metadata
