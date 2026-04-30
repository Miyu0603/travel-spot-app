from datetime import datetime
from pydantic import BaseModel
from app.models.spot import RegionEnum, ContinentEnum


class SpotBase(BaseModel):
    title: str
    description: str = ""
    address: str = ""
    latitude: float | None = None
    longitude: float | None = None
    google_maps_url: str = ""
    business_hours: str = ""
    notes: str = ""
    region: RegionEnum = RegionEnum.TAIWAN
    continent: ContinentEnum | None = None
    country: str = ""
    city: str = ""
    source_type: str = "manual"
    images: str = "[]"


class SpotCreate(SpotBase):
    tags: list[str] = []


class SpotUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    address: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    google_maps_url: str | None = None
    business_hours: str | None = None
    notes: str | None = None
    region: RegionEnum | None = None
    continent: ContinentEnum | None = None
    country: str | None = None
    city: str | None = None
    tags: list[str] | None = None


class SpotResponse(SpotBase):
    id: int
    source_id: int | None = None
    tags: list[str] = []
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}
