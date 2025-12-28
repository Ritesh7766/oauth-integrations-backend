# hubspot.py

import asyncio
import base64
import json
import secrets
from typing import Any
from urllib.parse import urlencode

from fastapi import HTTPException, Request
from fastapi.responses import HTMLResponse
import httpx

from redis_client import add_key_value_redis, delete_key_redis, get_value_redis
from settings import hubspot_settings


async def authorize_hubspot(user_id: str, org_id: str) -> str:
    state_data = {
        "state": secrets.token_urlsafe(32),
        "user_id": user_id,
        "org_id": org_id,
    }
    jsonified_state = json.dumps(state_data).encode("utf-8")
    encoded_state = base64.urlsafe_b64encode(jsonified_state).decode("utf-8")
    scope = "oauth"
    params = {
        "state": encoded_state,
        "scope": scope,
        "redirect_uri": hubspot_settings.redirect_uri,
    }
    auth_url = hubspot_settings.auth_url + urlencode(params)
    await add_key_value_redis(
        f"hubspot_state:{org_id}:{user_id}", jsonified_state, expire=600
    )
    return auth_url


async def oauth2callback_hubspot(request: Request) -> HTMLResponse:
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
    saved_state = await get_value_redis(f"hubspot_state:{org_id}:{user_id}")

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
            delete_key_redis(f"hubspot_state:{org_id}:{user_id}"),
        )
    await add_key_value_redis(
        f"airtable_credentials:{org_id}:{user_id}",
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


async def get_hubspot_credentials(user_id: str, org_id: str) -> dict[str, Any]:
    key = f"hubspot_credentials:{org_id}:{user_id}"

    raw = await get_value_redis(key)
    if raw is None:
        raise HTTPException(status_code=400, detail="No credentials found.")

    try:
        credentials = json.loads(raw)
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="Corrupted credentials data.")

    await delete_key_redis(key)
    return credentials


async def create_integration_item_metadata_object(response_json):
    # TODO
    pass


async def get_items_hubspot(credentials):
    # TODO
    pass
