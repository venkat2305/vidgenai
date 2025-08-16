from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime, timezone
from enum import Enum
import uuid


class VideoStatus(str, Enum):
    PENDING = "pending"
    GENERATING_SCRIPT = "generating_script"
    FETCHING_IMAGES = "fetching_images"
    GENERATING_AUDIO = "generating_audio"
    GENERATING_SUBTITLES = "generating_subtitles"
    COMPOSING_VIDEO = "composing_video"
    UPLOADING = "uploading"
    COMPLETED = "completed"
    FAILED = "failed"


class VideoModel(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    title: str
    celebrity_name: Optional[str] = None
    description: Optional[str] = None
    status: VideoStatus = VideoStatus.PENDING
    progress: int = 0  # 0-100%
    error_message: Optional[str] = None
    script: Optional[str] = None
    image_urls: List[str] = []
    audio_url: Optional[str] = None
    video_url: Optional[str] = None
    thumbnail_url: Optional[str] = None
    duration: Optional[float] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    step_timings: dict = Field(default_factory=dict)

    class Config:
        json_schema_extra = {
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "title": "Michael Jordan's Rise to Fame",
                "celebrity_name": "Michael Jordan",
                "description": "The incredible journey of basketball legend Michael Jordan",
                "status": "completed",
                "progress": 100,
                "video_url": "https://example.com/videos/michael-jordan.mp4",
                "thumbnail_url": "https://example.com/thumbnails/michael-jordan.jpg",
                "duration": 45.5,
                "created_at": "2023-05-01T12:00:00Z",
                "updated_at": "2023-05-01T12:05:30Z"
            }
        }


class VideoCreate(BaseModel):
    celebrity_name: str
    title: Optional[str] = None
    description: Optional[str] = None

    class Config:
        json_schema_extra = {
            "example": {
                "celebrity_name": "Michael Jordan",
                "title": "Michael Jordan's Rise to Fame",
                "description": "The incredible journey of basketball legend Michael Jordan"
            }
        }
