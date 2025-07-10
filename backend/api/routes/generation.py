from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from db.mongodb import mongodb
from db.models.video import VideoCreate, VideoModel, VideoStatus

import modal
import asyncio
import aiofiles

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
            audio_path, alignment_data = await audio_generator.generate_audio(script)

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
        subtitle_path = await subtitle_generator.generate(script, audio_path, alignment_data, temp_dir=temp_dir)

        # Upload subtitles
        upload_start = datetime.now(timezone.utc)
        try:
            subtitle_url = await upload_to_s3(subtitle_path, f"{video_id}.srt")
            step_timings["subtitle_upload"] = (datetime.now(timezone.utc) - upload_start).total_seconds()
        except Exception as upload_error:
            logger.error(f"Subtitle upload failed: {str(upload_error)}")
            step_timings["subtitle_upload_failed"] = (datetime.now(timezone.utc) - upload_start).total_seconds()

        step_timings["subtitle_generation"] = (datetime.now(timezone.utc) - start_time).total_seconds()
        await update_video_status(
            video_id,
            VideoStatus.GENERATING_SUBTITLES,
            80,
            subtitle_url=subtitle_url,
            step_timings=step_timings
        )

        # 5. Offload video composition to Modal
        await update_video_status(video_id, VideoStatus.COMPOSING_VIDEO, 85)
        start_time = datetime.now(timezone.utc)

        try:
            # Get a handle to the deployed Modal function
            f = modal.Function.lookup("video-generator", "generate_video")

            # Asynchronously call the Modal function
            modal_result = await f.remote.aio(
                image_urls=image_urls,
                audio_url=audio_url,
                subtitle_url=subtitle_url,
                script=script,
                video_aspect=aspect_ratio,
                apply_effects=apply_effects,
            )

            if not modal_result or not modal_result.get("success"):
                raise HTTPException(status_code=500, detail="Modal video generation failed.")

            video_url = modal_result["video_url"]
            thumbnail_url = modal_result["thumbnail_url"]
            
            # Use ffprobe to get the duration from the remote video URL
            # This is a simplified approach. For production, you might want a more robust way.
            proc = await asyncio.create_subprocess_exec(
                "ffprobe", "-v", "error", "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1", video_url,
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await proc.communicate()
            if proc.returncode == 0:
                duration = float(stdout.decode().strip())
            else:
                logger.warning(f"Could not probe video duration for {video_url}. Setting to 0.")
                duration = 0

            step_timings["video_composition_modal"] = (datetime.now(timezone.utc) - start_time).total_seconds()
            
            # Mark as completed since Modal handles the final upload
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
            logger.info(f"Modal video generation completed for {video_id} in {total_time:.2f} seconds")

        except Exception as modal_error:
            logger.error(f"Modal video generation failed for {video_id}: {str(modal_error)}", exc_info=True)
            await update_video_status(
                video_id,
                VideoStatus.FAILED,
                error_message=f"Modal generation failed: {str(modal_error)}",
            )
            return

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
