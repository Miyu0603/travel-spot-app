from sqlalchemy import Column, Integer, String, Text, DateTime, Enum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum

from app.database import Base


class PlatformEnum(str, enum.Enum):
    INSTAGRAM = "instagram"
    FACEBOOK = "facebook"
    THREADS = "threads"
    OTHER = "other"


class SourceStatusEnum(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class Source(Base):
    __tablename__ = "sources"

    id = Column(Integer, primary_key=True, index=True)
    url = Column(String(2000), nullable=False)
    platform = Column(Enum(PlatformEnum), default=PlatformEnum.OTHER)
    raw_content = Column(Text, default="")
    status = Column(Enum(SourceStatusEnum), default=SourceStatusEnum.PENDING)
    error_message = Column(Text, default="")

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    spots = relationship("Spot", back_populates="source")
