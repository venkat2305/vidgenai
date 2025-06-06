from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from db.mongodb import mongodb
from db.models.video import VideoCreate, VideoModel, VideoStatus

from services.video.composer import compose_video
from services.s3.storage import upload_to_s3
import logging
from datetime import datetime, timezone
import tempfile

from services.script.script_generator import ScriptGenerationService
from services.audio.audio_generator import AudioGenerator
from services.subtitles.subtitle_generator import SubtitleGenerator
from services.media.image_fetcher import ImageFetchService


router = APIRouter()
logger = logging.getLogger("vidgenai.generation")


async def update_video_status(
    video_id: str,
    status: VideoStatus,
    progress: int = None,
    error_message: str = None,
    step_timings: dict = None,
    **kwargs
):
    """ Update the status and other fields of a video in the database """
    videos_collection = mongodb.db.videos

    update_data = {
        "status": status,
        "updated_at": datetime.now(timezone.utc),
    }

    if progress is not None:
        update_data["progress"] = progress

    if error_message:
        update_data["error_message"] = error_message

    if step_timings:
        for step, duration in step_timings.items():
            update_data[f"step_timings.{step}"] = duration

    # Add any additional fields from kwargs
    update_data.update(kwargs)

    await videos_collection.update_one(
        {"id": video_id},
        {"$set": update_data}
    )


async def generate_video_background(video_id: str, aspect_ratio: str = "9:16", apply_effects: bool = True, use_contextual_images: bool = True):
    """Background task to generate a video with timing measurements for each step."""
    temp_dir_obj = tempfile.TemporaryDirectory()
    temp_dir = temp_dir_obj.name
    try:
        videos_collection = mongodb.db.videos
        video = await videos_collection.find_one({"id": video_id})

        if not video:
            logger.error(f"Video with ID {video_id} not found")
            return

        # Initialize timings dict
        step_timings = {}

        # 1. Generate script
        await update_video_status(video_id, VideoStatus.GENERATING_SCRIPT, 10)
        start_time = datetime.now(timezone.utc)
        script_generator = ScriptGenerationService()
        script = await script_generator.generate_script(video["celebrity_name"])
        step_timings["script_generation"] = (datetime.now(timezone.utc) - start_time).total_seconds()
        await update_video_status(
            video_id,
            VideoStatus.GENERATING_SCRIPT,
            20,
            script=script,
            step_timings=step_timings
        )

        # 2. Fetch images with metadata
        await update_video_status(video_id, VideoStatus.FETCHING_IMAGES, 30)
        start_time = datetime.now(timezone.utc)
        image_fetch_service = ImageFetchService()
        image_data = await image_fetch_service.fetch_images(
            video["celebrity_name"],
            script,
            num_images=8,
            aspect_ratio=aspect_ratio
        )
        image_urls = [img["url"] for img in image_data]
        step_timings["image_fetching"] = (datetime.now(timezone.utc) - start_time).total_seconds()
        await update_video_status(
            video_id,
            VideoStatus.FETCHING_IMAGES,
            40,
            image_urls=image_urls,
            step_timings=step_timings
        )

        # 3. Generate audio
        await update_video_status(video_id, VideoStatus.GENERATING_AUDIO, 50)
        start_time = datetime.now(timezone.utc)
        audio_url = None
        audio_path = None
        try:
            audio_generator = AudioGenerator(temp_dir=temp_dir)
            audio_path = await audio_generator.generate_audio(script)
            
            # Upload audio (optional)
            upload_start = datetime.now(timezone.utc)
            try:
                audio_url = await upload_to_s3(audio_path, f"{video_id}.mp3")
                step_timings["audio_upload"] = (datetime.now(timezone.utc) - upload_start).total_seconds()
            except Exception as upload_error:
                logger.error(f"Audio upload failed: {str(upload_error)}")
                step_timings["audio_upload_failed"] = (datetime.now(timezone.utc) - upload_start).total_seconds()
            
            step_timings["audio_generation"] = (datetime.now(timezone.utc) - start_time).total_seconds()
            await update_video_status(
                video_id,
                VideoStatus.GENERATING_AUDIO,
                60,
                audio_url=audio_url,
                step_timings=step_timings
            )
        except Exception as audio_error:
            step_timings["audio_generation_failed"] = (datetime.now(timezone.utc) - start_time).total_seconds()
            logger.error(f"Audio generation failed: {str(audio_error)}")
            await update_video_status(
                video_id,
                VideoStatus.FAILED,
                error_message=f"Audio generation failed: {str(audio_error)}",
                step_timings=step_timings
            )
            return

        # 4. Generate subtitles
        await update_video_status(video_id, VideoStatus.GENERATING_SUBTITLES, 70)
        start_time = datetime.now(timezone.utc)
        subtitle_generator = SubtitleGenerator()
        subtitle_path = await subtitle_generator.generate(script, audio_path, temp_dir=temp_dir)
        
        # Upload subtitles
        upload_start = datetime.now(timezone.utc)
        try:
            await upload_to_s3(subtitle_path, f"{video_id}.srt")
            step_timings["subtitle_upload"] = (datetime.now(timezone.utc) - upload_start).total_seconds()
        except Exception as upload_error:
            logger.error(f"Subtitle upload failed: {str(upload_error)}")
            step_timings["subtitle_upload_failed"] = (datetime.now(timezone.utc) - upload_start).total_seconds()
        
        step_timings["subtitle_generation"] = (datetime.now(timezone.utc) - start_time).total_seconds()
        await update_video_status(
            video_id,
            VideoStatus.GENERATING_SUBTITLES,
            80,
            step_timings=step_timings
        )

        # 5. Compose video
        await update_video_status(video_id, VideoStatus.COMPOSING_VIDEO, 80)
        start_time = datetime.now(timezone.utc)
        video_path, thumbnail_path, duration = await compose_video(
            script,
            image_data,
            audio_path,
            subtitle_path,
            video_aspect=aspect_ratio,
            apply_effects=apply_effects,
            temp_dir=temp_dir,
        )
        step_timings["video_composition"] = (datetime.now(timezone.utc) - start_time).total_seconds()
        await update_video_status(
            video_id,
            VideoStatus.COMPOSING_VIDEO,
            90,
            step_timings=step_timings
        )

        # 6. Upload final assets
        await update_video_status(video_id, VideoStatus.UPLOADING, 90)
        start_time = datetime.now(timezone.utc)
        try:
            video_url = await upload_to_s3(video_path, f"{video_id}-video.mp4")
            thumbnail_url = await upload_to_s3(thumbnail_path, f"{video_id}-thumbnail.jpg")
            step_timings["final_upload"] = (datetime.now(timezone.utc) - start_time).total_seconds()
        except Exception as upload_error:
            logger.error(f"Final upload failed: {str(upload_error)}")
            step_timings["final_upload_failed"] = (datetime.now(timezone.utc) - start_time).total_seconds()
            raise

        # 7. Mark as completed
        total_time = sum(v for k, v in step_timings.items() if not k.endswith("_failed"))
        step_timings["total_processing_time"] = total_time

        await update_video_status(
            video_id,
            VideoStatus.COMPLETED,
            100,
            video_url=video_url,
            thumbnail_url=thumbnail_url,
            duration=duration,
            step_timings=step_timings
        )

        logger.info(f"Video generation completed for {video_id} in {total_time:.2f} seconds")

    except Exception as e:
        logger.error(f"Error generating video {video_id}: {str(e)}", exc_info=True)
        if "step_timings" not in locals():
            step_timings = {}
        step_timings["error_occurred_at"] = datetime.now(timezone.utc).isoformat()
        await update_video_status(
            video_id,
            VideoStatus.FAILED,
            error_message=str(e),
            step_timings=step_timings
        )

    finally:
        temp_dir_obj.cleanup()


@router.post("/", response_model=VideoModel)
async def create_video_generation(
    video_data: VideoCreate,
    background_tasks: BackgroundTasks,
    aspect_ratio: str = Query("9:16", description="Video aspect ratio (9:16, 16:9, 1:1)"),
    apply_effects: bool = Query(True, description="Apply visual effects (zoom/pan) to images"),
    use_contextual_images: bool = Query(False, description="Use context-aware images that change with the script content")
):
    video = VideoModel(
        celebrity_name=video_data.celebrity_name,
        title=video_data.title or f"{video_data.celebrity_name}'s History",
        description=video_data.description or f"The history and achievements of {video_data.celebrity_name}"
    )

    videos_collection = mongodb.db.videos
    await videos_collection.insert_one(video.dict())

    background_tasks.add_task(generate_video_background, video.id, aspect_ratio, apply_effects, use_contextual_images)

    return video


@router.get("/{job_id}", response_model=VideoModel)
async def get_generation_status(job_id: str):
    videos_collection = mongodb.db.videos
    video = await videos_collection.find_one({"id": job_id})

    if not video:
        raise HTTPException(status_code=404, detail="Generation job not found")

    return video
