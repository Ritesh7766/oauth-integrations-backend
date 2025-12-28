# airtable.py

import asyncio
import base64
import hashlib
import json
import secrets
from typing import Any

from fastapi import HTTPException, Request, Response
from fastapi.responses import HTMLResponse
import httpx
import requests

from integrations.base import OAuthIntegration
from integrations.base.integration_item import IntegrationItem
from redis_client import add_key_value_redis, delete_key_redis, get_value_redis
from settings import airtable_settings


def create_integration_item_metadata_object(
    response_json: dict[str, Any], item_type: str, parent_id=None, parent_name=None
) -> IntegrationItem:
    parent_id = None if parent_id is None else parent_id + "_Base"
    integration_item_metadata = IntegrationItem(
        id=response_json.get("id", "") + "_" + item_type,
        name=response_json.get("name", None),
        type=item_type,
        parent_id=parent_id,
        parent_path_or_name=parent_name,
    )

    return integration_item_metadata


def fetch_items(
    access_token: str, url: str, aggregated_response: list, offset=None
) -> None:
    """Fetching the list of bases"""
    params = {"offset": offset} if offset is not None else {}
    headers = {"Authorization": f"Bearer {access_token}"}
    response = requests.get(url, headers=headers, params=params)

    if response.status_code == 200:
        results = response.json().get("bases", {})
        offset = response.json().get("offset", None)

        for item in results:
            aggregated_response.append(item)
        if offset is not None:
            fetch_items(access_token, url, aggregated_response, offset)
        else:
            return


class AirtableIntegration(OAuthIntegration):
    PREFIX = "airtable"

    async def authorize(self, user_id: str, org_id: str) -> str:
        state_data = {
            "state": secrets.token_urlsafe(32),
            "user_id": user_id,
            "org_id": org_id,
        }
        encoded_state = base64.urlsafe_b64encode(
            json.dumps(state_data).encode("utf-8")
        ).decode("utf-8")

        code_verifier = secrets.token_urlsafe(32)
        m = hashlib.sha256()
        m.update(code_verifier.encode("utf-8"))
        code_challenge = (
            base64.urlsafe_b64encode(m.digest()).decode("utf-8").replace("=", "")
        )
        scope = (
            "data.records:read data.records:write "
            "data.recordComments:read data.recordComments:write "
            "schema.bases:read schema.bases:write"
        )
        auth_url = (
            f"{airtable_settings.auth_url}"
            f"&state={encoded_state}"
            f"&code_challenge={code_challenge}"
            f"&code_challenge_method=S256"
            f"&scope={scope}"
        )
        await asyncio.gather(
            add_key_value_redis(
                f"{self.PREFIX}_state:{org_id}:{user_id}",
                json.dumps(state_data),
                expire=600,
            ),
            add_key_value_redis(
                f"{self.PREFIX}_verifier:{org_id}:{user_id}", code_verifier, expire=600
            ),
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

        saved_state, code_verifier = await asyncio.gather(
            get_value_redis(f"{self.PREFIX}_state:{org_id}:{user_id}"),
            get_value_redis(f"{self.PREFIX}_verifier:{org_id}:{user_id}"),
        )

        if not saved_state or original_state != json.loads(saved_state).get("state"):
            raise HTTPException(status_code=400, detail="State does not match.")

        async with httpx.AsyncClient() as client:
            encoded_client_id_secret = airtable_settings.encoded_client_id_secret
            response, _, _ = await asyncio.gather(
                client.post(
                    "https://airtable.com/oauth2/v1/token",
                    data={
                        "grant_type": "authorization_code",
                        "code": code,
                        "redirect_uri": airtable_settings.redirect_uri,
                        "client_id": airtable_settings.client_id,
                        "code_verifier": code_verifier.decode("utf-8"),
                    },
                    headers={
                        "Authorization": f"Basic {encoded_client_id_secret}",
                        "Content-Type": "application/x-www-form-urlencoded",
                    },
                ),
                delete_key_redis(f"{self.PREFIX}_state:{org_id}:{user_id}"),
                delete_key_redis(f"{self.PREFIX}_verifier:{org_id}:{user_id}"),
            )
        await add_key_value_redis(
            f"{self.PREFIX}_credentials:{org_id}:{user_id}",
            json.dumps(response.json()),
            expire=600,
        )

        return HTMLResponse(
            content="""
            <html>
                <script>window.close();</script>
            </html>
            """
        )

    async def get_items(self, credentials: str) -> list[IntegrationItem]:
        parsed_credentials = json.loads(credentials)
        url = "https://api.airtable.com/v0/meta/bases"
        list_of_integration_item_metadata = []
        list_of_responses: list[Response] = []

        fetch_items(parsed_credentials.get("access_token"), url, list_of_responses)
        for response in list_of_responses:
            list_of_integration_item_metadata.append(
                create_integration_item_metadata_object(response, "Base")
            )
            tables_response = requests.get(
                f'https://api.airtable.com/v0/meta/bases/{response.get("id")}/tables',
                headers={
                    "Authorization": f'Bearer {parsed_credentials.get("access_token")}'
                },
            )
            if tables_response.status_code == 200:
                tables_response = tables_response.json()
                for table in tables_response["tables"]:
                    list_of_integration_item_metadata.append(
                        create_integration_item_metadata_object(
                            table,
                            "Table",
                            response.get("id", None),
                            response.get("name", None),
                        )
                    )

        return list_of_integration_item_metadata
