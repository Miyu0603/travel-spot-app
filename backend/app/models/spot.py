import enum

from sqlalchemy import Column, Integer, String, Float, Text, DateTime, Enum, ForeignKey, Table
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class ContinentEnum(str, enum.Enum):
    ASIA = "asia"
    EUROPE = "europe"
    NORTH_AMERICA = "north_america"
    SOUTH_AMERICA = "south_america"
    OCEANIA = "oceania"
    AFRICA = "africa"


class RegionEnum(str, enum.Enum):
    TAIWAN = "taiwan"
    JAPAN = "japan"
    INTERNATIONAL = "international"


# Many-to-many: Spot <-> Tag
spot_tags = Table(
    "spot_tags",
    Base.metadata,
    Column("spot_id", Integer, ForeignKey("spots.id"), primary_key=True),
    Column("tag_id", Integer, ForeignKey("tags.id"), primary_key=True),
)


class Spot(Base):
    __tablename__ = "spots"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False, index=True)
    description = Column(Text, default="")
    address = Column(String(500), default="")
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    google_maps_url = Column(String(1000), default="")
    business_hours = Column(Text, default="")  # JSON string
    notes = Column(Text, default="")

    # Region classification
    region = Column(Enum(RegionEnum), default=RegionEnum.TAIWAN)
    continent = Column(Enum(ContinentEnum), nullable=True)  # Only for INTERNATIONAL
    country = Column(String(100), default="")
    city = Column(String(100), default="")

    # Source
    source_type = Column(String(20), default="manual")  # "url" | "manual"
    source_id = Column(Integer, ForeignKey("sources.id"), nullable=True)

    # Images (JSON array of URLs)
    images = Column(Text, default="[]")

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    source = relationship("Source", back_populates="spots")
    tags = relationship("Tag", secondary=spot_tags, back_populates="spots")


class Tag(Base):
    __tablename__ = "tags"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), unique=True, nullable=False)

    spots = relationship("Spot", secondary=spot_tags, back_populates="tags")
