from datetime import datetime

from pydantic import BaseModel


class IntegrationItem(BaseModel):
    id: str | None = None
    type: str | None = None
    directory: bool = False
    parent_path_or_name: str | None = None
    parent_id: str | None = None
    name: str | None = None
    creation_time: datetime | None = None
    last_modified_time: datetime | None = None
    url: str | None = None
    children: list[str] | None = None
    mime_type: str | None = None
    delta: str | None = None
    drive_id: str | None = None
    visibility: bool = True
