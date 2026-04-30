from datetime import datetime
from pydantic import BaseModel, HttpUrl
from app.models.source import PlatformEnum, SourceStatusEnum


class SourceCreate(BaseModel):
    url: str


class SourceManualCreate(BaseModel):
    """For manually pasting content when scraping fails."""
    url: str = ""
    platform: PlatformEnum = PlatformEnum.OTHER
    raw_content: str


class SourceResponse(BaseModel):
    id: int
    url: str
    platform: PlatformEnum
    status: SourceStatusEnum
    raw_content: str = ""
    error_message: str = ""
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class ScrapeResult(BaseModel):
    source: SourceResponse
    spots: list[dict] = []
    message: str = ""
