from fastapi import HTTPException

from integrations.integrations import (
    AirtableIntegration,
    HubSpotIntegration,
    NotionIntegration,
)

INTEGRATIONS = {
    "hubspot": HubSpotIntegration(),
    "notion": NotionIntegration(),
    "airtable": AirtableIntegration(),
}


def get_integration(name: str):
    try:
        return INTEGRATIONS[name]
    except KeyError:
        raise HTTPException(status_code=404, detail="Integration not supported")
