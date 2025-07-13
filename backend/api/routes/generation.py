import asyncio
import logging
import tempfile
import time
from datetime import datetime, timezone

import modal
from fastapi import APIRouter, BackgroundTasks, HTTPException, Query

from db.mongodb import mongodb
from db.models.video import VideoCreate, VideoModel, VideoStatus
from services.audio.audio_generator import AudioGenerator
from services.media.image_fetcher import ImageFetchService
from services.script.script_generator import ScriptGenerationService
from services.s3.storage import upload_to_s3
from services.subtitles.subtitle_generator import SubtitleGenerator


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
    """Optimized background task with parallel processing"""
    temp_dir_obj = tempfile.TemporaryDirectory()
    temp_dir = temp_dir_obj.name
    
    start_total_time = time.perf_counter()

    try:
        videos_collection = mongodb.db.videos
        video = await videos_collection.find_one({"id": video_id})
        
        if not video:
            logger.error(f"Video with ID {video_id} not found")
            return

        step_timings = {}
        
        # OPTIMIZATION 1: Run script generation and image fetching in parallel
        await update_video_status(video_id, VideoStatus.GENERATING_SCRIPT, 10)
        start_time = datetime.now(timezone.utc)
        
        # Wait for script first (needed for contextual images)
        script = await ScriptGenerationService().generate_script(video["celebrity_name"])
        step_timings["script_generation"] = (
            datetime.now(timezone.utc) - start_time
        ).total_seconds()

        # 2. Images second (always with the script if you want contextual images)
        await update_video_status(video_id, VideoStatus.FETCHING_IMAGES, 30)
        start_time = datetime.now(timezone.utc)
        image_data = await ImageFetchService().fetch_images(
            video["celebrity_name"],
            script if use_contextual_images else "",  # Pass script or empty string
            num_images=8,
            aspect_ratio=aspect_ratio,
        )

        image_urls = [img["url"] for img in image_data]
        step_timings["image_fetching"] = (
            datetime.now(timezone.utc) - start_time
        ).total_seconds()

        await update_video_status(video_id, VideoStatus.GENERATING_AUDIO, 40,
                                script=script, image_urls=image_urls, step_timings=step_timings)
        
        # OPTIMIZATION 2: Run audio generation and subtitle preparation in parallel
        start_time = datetime.now(timezone.utc)
        
        # Start audio generation
        audio_generator = AudioGenerator(temp_dir=temp_dir)
        audio_task = audio_generator.generate_audio(script)
        
        # Start subtitle generator initialization (it can prepare while audio generates)
        subtitle_generator = SubtitleGenerator()
        
        # Wait for audio to complete
        audio_path, alignment_data = await audio_task
        step_timings["audio_generation"] = (datetime.now(timezone.utc) - start_time).total_seconds()
        
        # OPTIMIZATION 3: Run uploads and subtitle generation in parallel
        upload_start = datetime.now(timezone.utc)
        
        # Start audio upload and subtitle generation simultaneously
        audio_upload_task = upload_to_s3(audio_path, f"{video_id}.mp3")
        subtitle_task = subtitle_generator.generate(script, audio_path, alignment_data, temp_dir=temp_dir)
        
        # Wait for both to complete
        audio_url, subtitle_path = await asyncio.gather(audio_upload_task, subtitle_task)
        
        step_timings["audio_upload"] = (datetime.now(timezone.utc) - upload_start).total_seconds()
        step_timings["subtitle_generation"] = (datetime.now(timezone.utc) - upload_start).total_seconds()
        
        # Upload subtitles
        subtitle_url = await upload_to_s3(subtitle_path, f"{video_id}.srt")
        
        await update_video_status(video_id, VideoStatus.COMPOSING_VIDEO, 80,
                                audio_url=audio_url, subtitle_url=subtitle_url, step_timings=step_timings)
        
        # Continue with Modal video generation...
        start_time = datetime.now(timezone.utc)

        try:
            # Get a handle to the deployed Modal function
            f = modal.Function.from_name("video-generator", "generate_video")

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
            
            # Get duration from Modal response - Modal already calculates this from audio file
            duration = modal_result.get("duration", 0)
            if duration == 0:
                logger.warning(f"No duration provided by Modal for {video_url}. This is unexpected.")

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
        end_total_time = time.perf_counter()
        step_timings["total_processing_time"] = (end_total_time - start_total_time)
        logger.info(f"Total optimized video generation time for {video_id}: {(end_total_time - start_total_time):.2f} seconds")
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
