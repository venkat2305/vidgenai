from fastapi import APIRouter, BackgroundTasks, HTTPException, Depends
from app.db.mongodb import mongodb
from app.db.models.video import VideoCreate, VideoModel, VideoStatus
from app.services.script.script_generator import generate_script
from app.services.media.image_fetcher import fetch_images
from app.services.audio.audio_generator import generate_audio
from app.services.subtitles.subtitle_generator import generate_subtitles
from app.services.video.composer import compose_video
from app.services.s3.storage import upload_to_s3
import logging
from datetime import datetime

router = APIRouter()
logger = logging.getLogger("vidgenai.generation")


async def update_video_status(video_id: str, status: VideoStatus, progress: int = None, error_message: str = None, **kwargs):
    """ Update the status and other fields of a video in the database """
    videos_collection = mongodb.db.videos

    update_data = {
        "status": status,
        "updated_at": datetime.utcnow()
    }

    if progress is not None:
        update_data["progress"] = progress

    if error_message:
        update_data["error_message"] = error_message

    # Add any additional fields from kwargs
    update_data.update(kwargs)

    await videos_collection.update_one(
        {"id": video_id},
        {"$set": update_data}
    )


async def generate_video_background(video_id: str):
    """Background task to generate a video."""
    try:
        videos_collection = mongodb.db.videos
        video = await videos_collection.find_one({"id": video_id})
        
        if not video:
            logger.error(f"Video with ID {video_id} not found")
            return

        # 1. Generate script
        await update_video_status(video_id, VideoStatus.GENERATING_SCRIPT, 10)
        script = await generate_script(video["celebrity_name"])
        await update_video_status(video_id, VideoStatus.GENERATING_SCRIPT, 20, script=script)

        # 2. Fetch images
        await update_video_status(video_id, VideoStatus.FETCHING_IMAGES, 30)
        image_urls = await fetch_images(video["celebrity_name"], script)
        await update_video_status(video_id, VideoStatus.FETCHING_IMAGES, 40, image_urls=image_urls)

        # 3. Generate audio
        audio_url = None
        audio_path = None
        try:
            await update_video_status(video_id, VideoStatus.GENERATING_AUDIO, 50)
            audio_path = await generate_audio(script)
            print("Audio path:", audio_path)

            # Don't halt the entire process on upload failure
            try:
                audio_url = await upload_to_s3(audio_path, f"{video_id}.mp3")
                await update_video_status(video_id, VideoStatus.GENERATING_AUDIO, 60, audio_url=audio_url)
            except Exception as upload_error:
                logger.error(f"Failed to upload audio to S3/R2: {str(upload_error)}. Continuing with local audio file.")
                await update_video_status(
                    video_id, 
                    VideoStatus.GENERATING_AUDIO, 
                    60,
                    error_message=f"Audio generated but upload failed: {str(upload_error)}"
                )
        except Exception as audio_error:
            logger.error(f"Error in audio generation: {str(audio_error)}")
            await update_video_status(
                video_id,
                VideoStatus.FAILED, 
                error_message=f"Audio generation failed: {str(audio_error)}"
            )
            return

        # 4. Generate subtitles
        await update_video_status(video_id, VideoStatus.GENERATING_SUBTITLES, 70)
        subtitle_path = await generate_subtitles(script, audio_path)
        subtitle_url = await upload_to_s3(subtitle_path, f"{video_id}.srt")

        # 5. Compose video
        await update_video_status(video_id, VideoStatus.COMPOSING_VIDEO, 80)
        video_path, thumbnail_path, duration = await compose_video(
            script, image_urls, audio_path, subtitle_path
        )

        # 6. Upload to S3
        await update_video_status(video_id, VideoStatus.UPLOADING, 90)
        video_url = await upload_to_s3(video_path, f"{video_id}-video.mp4")
        thumbnail_url = await upload_to_s3(thumbnail_path, f"{video_id}-thumbnail.jpg")

        # 7. Mark as completed
        await update_video_status(
            video_id,
            VideoStatus.COMPLETED,
            100,
            video_url=video_url,
            thumbnail_url=thumbnail_url,
            duration=duration
        )

        logger.info(f"Video generation completed for {video_id}")

    except Exception as e:
        logger.error(f"Error generating video {video_id}: {str(e)}", exc_info=True)
        await update_video_status(video_id, VideoStatus.FAILED, error_message=str(e))


@router.post("/", response_model=VideoModel)
async def create_video_generation(
    video_data: VideoCreate,
    background_tasks: BackgroundTasks
):
    """
    Start the generation of a new video.
    """
    # Create a new video document
    video = VideoModel(
        celebrity_name=video_data.celebrity_name,
        title=video_data.title or f"{video_data.celebrity_name}'s History",
        description=video_data.description or f"The history and achievements of {video_data.celebrity_name}"
    )

    # Insert into database
    videos_collection = mongodb.db.videos
    await videos_collection.insert_one(video.dict())

    # Start background task
    background_tasks.add_task(generate_video_background, video.id)

    return video


@router.get("/{job_id}", response_model=VideoModel)
async def get_generation_status(job_id: str):
    """
    Check the status of a video generation job.
    """
    videos_collection = mongodb.db.videos
    video = await videos_collection.find_one({"id": job_id})

    if not video:
        raise HTTPException(status_code=404, detail="Generation job not found")

    return video
