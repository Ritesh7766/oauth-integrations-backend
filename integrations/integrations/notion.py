# notion.py

import asyncio
import json
import secrets
from typing import Any

from fastapi import HTTPException, Request
from fastapi.responses import HTMLResponse
import httpx

from integrations.base import IntegrationItem, OAuthIntegration
from redis_client import add_key_value_redis, delete_key_redis, get_value_redis
from settings import notion_settings


def recursive_dict_search(data: list | dict[str, Any], target_key: str) -> Any | None:
    """Recursively search for a key in a dictionary of dictionaries."""
    if isinstance(data, dict):
        if target_key in data:
            return data[target_key]

        for value in data.values():
            result = recursive_dict_search(value, target_key)
            if result is not None:
                return result

    elif isinstance(data, list):
        for item in data:
            result = recursive_dict_search(item, target_key)
            if result is not None:
                return result

    return None


def create_integration_item_metadata_object(
    response_json: dict[str, Any],
) -> IntegrationItem:
    """creates an integration metadata object from the response"""
    name = recursive_dict_search(response_json["properties"], "content")
    parent_type = (
        ""
        if response_json["parent"]["type"] is None
        else response_json["parent"]["type"]
    )
    parent_id = (
        None
        if response_json["parent"]["type"] == "workspace"
        else response_json["parent"][parent_type]
    )

    name = recursive_dict_search(response_json, "content") if name is None else name
    name = "multi_select" if name is None else name
    name = response_json["object"] + " " + name

    integration_item_metadata = IntegrationItem(
        id=response_json["id"],
        type=response_json["object"],
        name=name,
        creation_time=response_json["created_time"],
        last_modified_time=response_json["last_edited_time"],
        parent_id=parent_id,
    )

    return integration_item_metadata


class NotionIntegration(OAuthIntegration):
    PREFIX = "notion"

    async def authorize(self, user_id: str, org_id: str) -> str:
        state_data = {
            "state": secrets.token_urlsafe(32),
            "user_id": user_id,
            "org_id": org_id,
        }

        encoded_state = json.dumps(state_data)

        await add_key_value_redis(
            f"{self.PREFIX}_state:{org_id}:{user_id}",
            encoded_state,
            expire=self.STATE_TTL,
        )

        return f"{notion_settings.auth_url}&state={encoded_state}"

    async def oauth2callback(self, request: Request) -> HTMLResponse:
        if request.query_params.get("error"):
            raise HTTPException(
                status_code=400, detail=request.query_params.get("error")
            )
        code = request.query_params.get("code")
        encoded_state = request.query_params.get("state")
        state_data = json.loads(encoded_state.encode("utf-8").decode("unicode_escape"))

        original_state, user_id, org_id = (
            state_data.get("state"),
            state_data.get("user_id"),
            state_data.get("org_id"),
        )

        saved_state = await get_value_redis(f"{self.PREFIX}_state:{org_id}:{user_id}")

        if not saved_state or original_state != json.loads(saved_state).get("state"):
            raise HTTPException(status_code=400, detail="State does not match.")

        async with httpx.AsyncClient() as client:
            encoded_client_id_secret = notion_settings.encoded_client_id_secret
            response, _ = await asyncio.gather(
                client.post(
                    "https://api.notion.com/v1/oauth/token",
                    json={
                        "grant_type": "authorization_code",
                        "code": code,
                        "redirect_uri": notion_settings.redirect_uri,
                    },
                    headers={
                        "Authorization": f"Basic {encoded_client_id_secret}",
                        "Content-Type": "application/json",
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
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.notion.com/v1/search",
                headers={
                    "Authorization": f"Bearer {parsed_credentials.get('access_token')}",
                    "Notion-Version": "2022-06-28",
                },
            )

        response.raise_for_status()
        results = response.json().get("results", [])

        list_of_integration_item_metadata = [
            create_integration_item_metadata_object(result) for result in results
        ]
        print(list_of_integration_item_metadata)
        return list_of_integration_item_metadata
