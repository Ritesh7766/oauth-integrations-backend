# notion.py

import json
import secrets
from typing import Any
from fastapi import Request, HTTPException
from fastapi.responses import HTMLResponse
import httpx
import asyncio
import requests
from integrations.integration_item import IntegrationItem
from settings import notion_settings

from redis_client import add_key_value_redis, get_value_redis, delete_key_redis


async def authorize_notion(user_id: str, org_id: str) -> str:
    state_data = {
        "state": secrets.token_urlsafe(32),
        "user_id": user_id,
        "org_id": org_id,
    }
    encoded_state = json.dumps(state_data)
    await add_key_value_redis(
        f"notion_state:{org_id}:{user_id}", encoded_state, expire=600
    )

    return f"{notion_settings.auth_url}&state={encoded_state}"


async def oauth2callback_notion(request: Request) -> HTMLResponse:
    if request.query_params.get("error"):
        raise HTTPException(status_code=400, detail=request.query_params.get("error"))
    code = request.query_params.get("code")
    encoded_state = request.query_params.get("state")
    state_data = json.loads(encoded_state)

    original_state = state_data.get("state")
    user_id = state_data.get("user_id")
    org_id = state_data.get("org_id")

    saved_state = await get_value_redis(f"notion_state:{org_id}:{user_id}")

    if not saved_state or original_state != json.loads(saved_state).get("state"):
        raise HTTPException(status_code=400, detail="State does not match.")

    async with httpx.AsyncClient() as client:
        response, _ = await asyncio.gather(
            client.post(
                "https://api.notion.com/v1/oauth/token",
                json={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": notion_settings.redirect_uri,
                },
                headers={
                    "Authorization": f"Basic {notion_settings.encoded_client_id_secret}",
                    "Content-Type": "application/json",
                },
            ),
            delete_key_redis(f"notion_state:{org_id}:{user_id}"),
        )

    await add_key_value_redis(
        f"notion_credentials:{org_id}:{user_id}",
        json.dumps(response.json()),
        expire=600,
    )

    close_window_script = """
    <html>
        <script>
            window.close();
        </script>
    </html>
    """
    return HTMLResponse(content=close_window_script)


async def get_notion_credentials(user_id: str, org_id: str):
    credentials = await get_value_redis(f"notion_credentials:{org_id}:{user_id}")
    if not credentials:
        raise HTTPException(status_code=400, detail="No credentials found.")
    credentials = json.loads(credentials)
    if not credentials:
        raise HTTPException(status_code=400, detail="No credentials found.")
    await delete_key_redis(f"notion_credentials:{org_id}:{user_id}")

    return credentials


def _recursive_dict_search(data: dict[str, Any], target_key: str) -> Any | None:
    """Recursively search for a key in a dictionary of dictionaries."""
    if target_key in data:
        return data[target_key]

    for value in data.values():
        if isinstance(value, dict):
            result = _recursive_dict_search(value, target_key)
            if result is not None:
                return result
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    result = _recursive_dict_search(item, target_key)
                    if result is not None:
                        return result
    return None


def create_integration_item_metadata_object(
    response_json: dict[str, Any],
) -> IntegrationItem:
    """creates an integration metadata object from the response"""
    name = _recursive_dict_search(response_json["properties"], "content")
    parent_type = (
        ""
        if response_json["parent"]["type"] is None
        else response_json["parent"]["type"]
    )
    if response_json["parent"]["type"] == "workspace":
        parent_id = None
    else:
        parent_id = response_json["parent"][parent_type]

    name = _recursive_dict_search(response_json, "content") if name is None else name
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


async def get_items_notion(credentials: str) -> list[IntegrationItem] | None:
    """Aggregates all metadata relevant for a notion integration"""
    parsed_credentials = json.loads(credentials)
    response = requests.post(
        "https://api.notion.com/v1/search",
        headers={
            "Authorization": f'Bearer {parsed_credentials.get("access_token")}',
            "Notion-Version": "2022-06-28",
        },
    )

    if response.status_code == 200:
        results = response.json()["results"]
        list_of_integration_item_metadata = []
        for result in results:
            list_of_integration_item_metadata.append(
                create_integration_item_metadata_object(result)
            )

        print(list_of_integration_item_metadata)
        return list_of_integration_item_metadata
    return None
