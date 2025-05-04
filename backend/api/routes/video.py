from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
from db.mongodb import mongodb
from db.models.video import VideoModel

router = APIRouter()


@router.get("/", response_model=List[VideoModel])
async def get_videos(
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    status: Optional[str] = None
):
    query = {}
    if status:
        query["status"] = status

    videos_collection = mongodb.db.videos
    videos = await videos_collection.find(query).skip(skip).limit(limit).to_list(limit)

    return videos


@router.get("/{video_id}", response_model=VideoModel)
async def get_video(video_id: str):
    videos_collection = mongodb.db.videos
    video = await videos_collection.find_one({"id": video_id})

    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    return video
