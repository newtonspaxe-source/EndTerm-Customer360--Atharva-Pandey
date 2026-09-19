from datetime import datetime

from pydantic import BaseModel, ConfigDict


class Event(BaseModel):
    model_config = ConfigDict(extra="allow")

    event_id: str
    event_time: datetime
    ingestion_time: datetime
    customer_id: str
    account_id: str | None
    source_system: str
    event_type: str
    schema_version: str
    payload: dict