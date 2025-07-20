import modal
import os
import tempfile
import logging
import asyncio
import httpx
import aiofiles
from PIL import Image
import random
from typing import List, Tuple, Dict, Optional, Any
import io
import hashlib
from datetime import datetime
import time # Import time for accurate timing
from pathlib import Path


# ---- Quality Presets ----
PRESETS = {
    "low": {
        "crf": 30,
        "preset": "fast",
        "tune": "film",
        "profile": "baseline",
        "level": "3.0",
        "maxrate": "1M",
        "bufsize": "2M",
        "resolution": {
            "9:16": (480, 854),   # 480p vertical
            "16:9": (854, 480),   # 480p horizontal
            "1:1": (480, 480),    # 480p square
        }
    },
    "medium": {
        "crf": 25,
        "preset": "medium",
        "tune": "film",
        "profile": "main",
        "level": "3.1",
        "maxrate": "2M",
        "bufsize": "4M",
        "resolution": {
            "9:16": (720, 1280),  # 720p vertical
            "16:9": (1280, 720),  # 720p horizontal
            "1:1": (720, 720),    # 720p square
        }
    },
    "high": {
        "crf": 18,
        "preset": "slow",
        "tune": "film",
        "profile": "high",
        "level": "4.0",
        "maxrate": "5M",
        "bufsize": "10M",
        "resolution": {
            "9:16": (1080, 1920),  # 1080p vertical
            "16:9": (1920, 1080),  # 1080p horizontal
            "1:1": (1080, 1080),   # 1080p square
        }
    }
}


# ---- 1. Optimized Image with Minimal Dependencies ----
image = (
    modal.Image.debian_slim()
    .apt_install("ffmpeg")
    .pip_install(
        "Pillow",      # Lightweight image processing (50MB vs OpenCV's 150MB)
        "httpx",       # Async HTTP client (5MB vs boto3's 60MB)
        "aiofiles",    # Async file operations
        "boto3",       # AWS SDK for R2 uploads
    )
)

app = modal.App("video-generator", image=image)
logger = logging.getLogger("vidgenai.modal_worker")


# ---- 2. R2 Upload Function ----
async def upload_to_r2(file_path: str, object_key: str) -> str:
    # Configuration is loaded from Modal secrets
    R2_ACCESS_KEY_ID = os.environ["R2_ACCESS_KEY_ID"]
    R2_SECRET_ACCESS_KEY = os.environ["R2_SECRET_ACCESS_KEY"]
    R2_BUCKET_NAME = os.environ["R2_BUCKET_NAME"]
    R2_ENDPOINT_URL = os.environ["R2_ENDPOINT_URL"]
    R2_PUBLIC_URL_BASE = os.environ["R2_PUBLIC_URL_BASE"]

    try:
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        # Import boto3 here to avoid issues with async
        import boto3
        
        r2_client = boto3.client(
            's3',
            endpoint_url=R2_ENDPOINT_URL,
            aws_access_key_id=R2_ACCESS_KEY_ID,
            aws_secret_access_key=R2_SECRET_ACCESS_KEY,
            region_name="auto",
        )
        r2_client.upload_file(
            file_path,
            R2_BUCKET_NAME,
            object_key,
            ExtraArgs={'ACL': 'public-read'}
        )
        url = f"{R2_PUBLIC_URL_BASE}/{object_key}"
        logger.info(f"Successfully uploaded {file_path} to {url}")
        return url
    except Exception as e:
        logger.error(f"Failed to upload {file_path} to R2: {e}")
        raise


# ---- 3. Single-Pass Video Generation ----
class SinglePassVideoGenerator:
    def __init__(self):
        pass
        
    async def _run_command(self, cmd: List[str]) -> str:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            raise Exception(f"Command failed: {stderr.decode()}")
        return stdout.decode()
    
    def _get_video_dimensions(self, aspect_ratio: str, quality: str = "low") -> Tuple[int, int]:
        quality_preset = PRESETS.get(quality, PRESETS["low"])
        resolution = quality_preset["resolution"]
        return resolution.get(aspect_ratio, resolution["9:16"])
    
    def _build_effect_filter(
        self, index: int, duration: float, width: int, height: int, 
        effect_type: str
    ) -> str:
        """Build effect filter for a single image"""
        fps = 30
        frames = int(duration * fps)
        
        # Base scaling and padding - clean format
        base_filter = (
            f"[{index}:v]scale={width}:{height}:"
            f"force_original_aspect_ratio=decrease,"
            f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:black"
        )
        
        # Add effect based on type - zoompan handles duration internally
        if effect_type == "zoom_in":
            effect = (
                f"zoompan=z='min(zoom+0.0015,1.3)':"
                f"d={frames}:s={width}x{height}:fps={fps}"
            )
        elif effect_type == "zoom_out":
            effect = (
                f"zoompan=z='if(eq(on,1),1.3,max(1.001,zoom-0.0015))':"
                f"d={frames}:s={width}x{height}:fps={fps}"
            )
        elif effect_type == "pan_left":
            effect = (
                f"zoompan=z='1.2':x='if(gte(on,1),(on-1)*2,0)':"
                f"d={frames}:s={width}x{height}:fps={fps}"
            )
        elif effect_type == "pan_right":
            effect = (
                f"zoompan=z='1.2':"
                f"x='if(gte(on,1),iw-ow-(on-1)*2,iw-ow)':"
                f"d={frames}:s={width}x{height}:fps={fps}"
            )
        else:  # ken_burns - combination
            effect = (
                f"zoompan=z='min(zoom+0.001,1.2)':"
                f"x='if(gte(zoom,1.2),x+1,x)':y='if(gte(zoom,1.2),y+1,y)':"
                f"d={frames}:s={width}x{height}:fps={fps}"
            )
        
        # SAR normalization and pixel format fix
        post_filter = f"setsar=1,setdar={width}/{height},format=yuv420p"
        
        # Combine all parts and set PTS
        return f"{base_filter},{effect},{post_filter},setpts=PTS-STARTPTS[v{index}]"
    
    def _get_random_effect(self) -> str:
        """Get a random effect type"""
        effects = ["zoom_in", "zoom_out", "pan_left", "pan_right", "ken_burns"]
        return random.choice(effects)
    
    async def generate_video(
        self,
        image_paths: List[str],
        durations: List[float],
        audio_path: str,
        subtitle_path: str,
        output_path: str,
        video_aspect: str = "9:16",
        apply_effects: bool = True,
        quality: str = "low"
    ) -> Tuple[str, float]:
        """Generate video in a single FFmpeg pass"""
        
        width, height = self._get_video_dimensions(video_aspect, quality)
        
        print(f"Processing {len(image_paths)} images with durations: {durations}")
        
        # Build FFmpeg command
        cmd = ["ffmpeg", "-y"]
        
        # Add inputs WITHOUT loop flags - let filters handle duration
        filter_parts = []
        for i, (img_path, duration) in enumerate(zip(image_paths, durations)):
            cmd.extend(["-i", img_path])  # Remove -loop 1 -t duration flags
            print(f"Added input {i}: {img_path} for {duration}s")
            
            # Build filter for this image
            if apply_effects:
                effect_type = self._get_random_effect()
                filter_parts.append(
                    self._build_effect_filter(
                        i, duration, width, height, effect_type
                    )
                )
            else:
                # Simple scale and pad with duration
                fps = 30
                frames = int(duration * fps)
                filter_parts.append(
                    f"[{i}:v]scale={width}:{height}:force_original_aspect_ratio=decrease,"
                    f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:black,"
                    f"loop=loop={frames}:size=1:start=0,"
                    f"fps=30,setsar=1,setdar={width}/{height},format=yuv420p,"
                    f"setpts=PTS-STARTPTS[v{i}]"
                )
        
        # Add audio input
        audio_index = len(image_paths)
        cmd.extend(["-i", audio_path])
        
        # Build concatenation filter
        concat_inputs = "".join([f"[v{i}]" for i in range(len(image_paths))])
        concat_filter = (
            f"{concat_inputs}concat=n={len(image_paths)}:v=1:a=0[outv]"
        )
        print(f"Concatenating {len(image_paths)} video segments")
        
        # Add subtitles
        subtitle_filter = (
            f"[outv]subtitles='{subtitle_path}':force_style="
            f"'Fontsize=24,PrimaryColour=&HFFFFFF&,OutlineColour=&H000000&,"
            f"Outline=2,Alignment=2,MarginV=40'[final]"
        )
        
        # Combine all filters
        filter_complex = ";".join(
            filter_parts + [concat_filter, subtitle_filter]
        )
        
        print("Filter complex:", filter_complex[:200] + "..." if len(filter_complex) > 200 else filter_complex)
        
        # Add filter complex to command
        cmd.extend(["-filter_complex", filter_complex])
        
        # Map outputs
        cmd.extend(["-map", "[final]", "-map", f"{audio_index}:a"])
        
        # Get quality preset settings
        quality_settings = PRESETS.get(quality, PRESETS["low"])
        
        # CPU-only output settings with quality preset
        cmd.extend([
            "-c:v", "libx264",
            "-preset", quality_settings["preset"],
            "-crf", str(quality_settings["crf"]),
            "-tune", quality_settings["tune"],
            "-profile:v", quality_settings["profile"],
            "-level", quality_settings["level"],
            "-maxrate", quality_settings["maxrate"],
            "-bufsize", quality_settings["bufsize"],
        ])
        
        # Audio settings
        cmd.extend([
            "-c:a", "aac",
            "-b:a", "128k",
            "-ar", "44100",
            "-shortest",  # Match video length to shortest input
            output_path
        ])
        
        print("Running FFmpeg command with", len(cmd), "arguments")
        print("Command preview:", " ".join(cmd[:10]) + "...")
        
        # Run the command
        start_time = asyncio.get_event_loop().time()
        await self._run_command(cmd)
        duration = asyncio.get_event_loop().time() - start_time
        
        print(f"FFmpeg command completed in {duration:.2f} seconds")
        
        return output_path, duration


# ---- 4. Optimized Image Preprocessing ----
async def preprocess_images(image_urls: List[str], temp_dir: str) -> List[str]:
    """Download and preprocess images efficiently"""
    
    async def download_and_process(
        session: httpx.AsyncClient, url: str, index: int
    ) -> Optional[str]:
        try:
            output_path = os.path.join(temp_dir, f"img_{index:03d}.jpg")
            
            # Download image
            response = await session.get(url)
            response.raise_for_status()
            
            # Process with Pillow (more efficient than OpenCV for basic ops)
            img = Image.open(io.BytesIO(response.content))
            
            # Convert to RGB if necessary
            if img.mode != 'RGB':
                img = img.convert('RGB')
            
            # Save as optimized JPEG
            img.save(output_path, "JPEG", quality=95, optimize=True)
            
            logger.info(f"Downloaded and processed image {index} from {url}")
            return output_path
            
        except Exception as e:
            logger.error(f"Failed to process image {url}: {e}")
            return None
    
    # Download all images concurrently
    async with httpx.AsyncClient(timeout=30.0) as session:
        tasks = [
            download_and_process(session, url, i) 
            for i, url in enumerate(image_urls)
        ]
        results = await asyncio.gather(*tasks)
    
    # Filter out None values
    valid_paths = [path for path in results if path is not None]
    
    if not valid_paths:
        raise Exception("No images could be downloaded")
    
    return valid_paths


# ---- 5. Main Video Generation Function ----
async def generate_optimized_video(
    image_urls: List[str],
    audio_url: str,
    subtitle_url: str,
    script: str,
    video_aspect: str = "9:16",
    apply_effects: bool = True,
    quality: str = "low"
) -> Dict[str, Any]:
    """Main function to generate video with optimizations"""
    
    overall_start_time = time.time() # Start timing the entire process
    timings = {}
    
    with tempfile.TemporaryDirectory() as temp_dir:
        # Change to temp directory for simpler paths
        original_cwd = os.getcwd()
        os.chdir(temp_dir)
        
        try:
            # Download audio and subtitles concurrently
            start_time = time.time()
            async with httpx.AsyncClient(timeout=60.0) as client:
                print("Downloading audio and subtitles concurrently")
                audio_response = await client.get(audio_url)
                subtitle_response = await client.get(subtitle_url)
                
                audio_response.raise_for_status()
                subtitle_response.raise_for_status()
                
                # Save files
                audio_path = "audio.mp3"
                subtitle_path = "subtitles.srt"
                
                async with aiofiles.open(audio_path, "wb") as f:
                    await f.write(audio_response.content)
                
                async with aiofiles.open(subtitle_path, "wb") as f:
                    await f.write(subtitle_response.content)
            end_time = time.time()
            timings["audio_subtitle_download"] = end_time - start_time
            print("Downloaded audio and subtitles")
            logger.info(f"Audio and subtitle download took {timings['audio_subtitle_download']:.2f} seconds")
            
            # Get audio duration
            start_time = time.time()
            probe_cmd = [
                "ffprobe", "-v", "error", "-show_entries", 
                "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", 
                audio_path
            ]
            proc = await asyncio.create_subprocess_exec(
                *probe_cmd, stdout=asyncio.subprocess.PIPE
            )
            stdout, _ = await proc.communicate()
            total_duration = float(stdout.decode().strip())
            end_time = time.time()
            timings["get_audio_duration"] = end_time - start_time
            print("Got audio duration")
            logger.info(f"Getting audio duration took {timings['get_audio_duration']:.2f} seconds")
            
            # Preprocess images
            start_time = time.time()
            image_paths = await preprocess_images(image_urls, temp_dir)
            print("image_paths", image_paths)
            end_time = time.time()
            timings["image_preprocessing"] = end_time - start_time
            print("Preprocessed images")
            logger.info(f"Image preprocessing took {timings['image_preprocessing']:.2f} seconds")
            
            # Calculate duration per image
            durations = [total_duration / len(image_paths)] * len(image_paths)
            print("Calculated duration per image")
            
            # Generate video using single-pass approach
            generator = SinglePassVideoGenerator()
            video_path = "output.mp4"
            
            print("Generated video using single-pass approach")
            
            start_time = time.time()
            _, generation_time = await generator.generate_video(
                image_paths=image_paths,
                durations=durations,
                audio_path=audio_path,
                subtitle_path=subtitle_path,
                output_path=video_path,
                video_aspect=video_aspect,
                apply_effects=apply_effects,
                quality=quality
            )
            end_time = time.time()
            timings["video_generation"] = end_time - start_time
            
            print(f"Video generated in {generation_time:.2f} seconds")
            logger.info(f"Video generation completed in {timings['video_generation']:.2f} seconds")
            
            # Use the first image as the thumbnail
            thumbnail_path = image_paths[0]
            
            print("Using the first image as thumbnail")
            
            # Upload to R2
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # Use deterministic hash for consistent naming
            script_hash = hashlib.md5(script.encode()).hexdigest()[:8]
            video_key = f"videos/{timestamp}_{script_hash}.mp4"
            thumb_key = f"thumbnails/{timestamp}_{script_hash}.jpg"
            
            start_time = time.time()
            video_url = await upload_to_r2(video_path, video_key)
            end_time = time.time()
            timings["video_upload_to_r2"] = end_time - start_time
            
            start_time = time.time()
            thumb_url = await upload_to_r2(
                thumbnail_path, thumb_key
            )
            end_time = time.time()
            timings["thumbnail_upload_to_r2"] = end_time - start_time
            
            print("Video generated successfully")
            logger.info("--- Video Generation Timings Summary ---")
            for step, duration in timings.items():
                logger.info(f"{step.replace('_', ' ').title()}: {duration:.2f} seconds")
            logger.info("----------------------------------------")
            
            overall_end_time = time.time() # End timing the entire process
            total_process_time = overall_end_time - overall_start_time
            
            # Calculate total generation time from all individual timings
            total_video_generation_time = sum(timings.values())
            
            logger.info(f"Total process time: {total_process_time:.2f} seconds")
            logger.info(f"Total effective video generation time (sum of steps): {total_video_generation_time:.2f} seconds")
            
            return {
                "success": True,
                "video_url": video_url,
                "thumbnail_url": thumb_url,
                "duration": total_duration,
                "generation_time": generation_time,
                "timings_summary": timings, # Include timings in the result
                "total_process_time": total_process_time, # Total time for the entire function execution
                "total_video_generation_time": total_video_generation_time # Sum of all individual timed steps
            }
            
        finally:
            os.chdir(original_cwd)


# ---- 6. Modal Function ----
@app.function(
    cpu=8.0,        # More CPU for CPU-only processing
    memory=2048,    # More memory for CPU processing
    retries=0,
    secrets=[modal.Secret.from_name("r2-credentials")],
    timeout=900,
    max_containers=20,
)
async def generate_video(
    image_urls: List[str],
    audio_url: str,
    subtitle_url: str,
    script: str,
    video_aspect: str = "9:16",
    apply_effects: bool = True,
    quality: str = "low",
):
    """Modal endpoint for video generation"""
    
    logger.info("Starting CPU-only video generation")
    
    try:
        result = await generate_optimized_video(
            image_urls=image_urls,
            audio_url=audio_url,
            subtitle_url=subtitle_url,
            script=script,
            video_aspect=video_aspect,
            apply_effects=apply_effects,
            quality=quality
        )
        
        logger.info(f"Video generation completed: {result}")
        return result
        
    except Exception as e:
        logger.error(f"Video generation failed: {e}")
        return {
            "success": False,
            "error": str(e)
        }


# ---- 7. Load Environment Variables ----
def load_env_file():
    """Load environment variables from .env file"""
    # Look for .env file in backend directory
    env_path = Path(__file__).parent.parent / "backend" / ".env"
    
    if env_path.exists():
        print(f"Loading environment variables from {env_path}")
        with open(env_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    # Remove quotes if present
                    value = value.strip('"\'')
                    os.environ[key] = value
        print("Environment variables loaded successfully")
    else:
        print(f"No .env file found at {env_path}")


# ---- 8. Test Entrypoint ----
async def run_local():
    """Test the optimized video generation locally"""
    from test_data import test_image_urls, test_audio_url, test_subtitle_url, test_script

    # Load environment variables from .env file
    load_env_file()

    # Check for necessary environment variables
    required_env_vars = [
        "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_BUCKET_NAME",
        "R2_ENDPOINT_URL", "R2_PUBLIC_URL_BASE"
    ]
    
    missing_vars = [var for var in required_env_vars if not os.getenv(var)]
    if missing_vars:
        print("Error: Missing the following R2 environment variables:")
        for var in missing_vars:
            print(f"  - {var}")
        print("\nPlease ensure these are set in backend/.env file")
        return

    test_data = {
        "image_urls": test_image_urls,
        "audio_url": test_audio_url,
        "subtitle_url": test_subtitle_url,
        "script": test_script,
        "video_aspect": "9:16",
        "apply_effects": True,
        "quality": "low"
    }

    print("Testing optimized video generation locally...")

    try:
        # We call generate_optimized_video directly, bypassing the modal-specific wrapper
        result = await generate_optimized_video(**test_data)
        print(f"Local Result: {result}")
    except Exception as e:
        print(f"Local test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    # This allows running the script directly with `python workers/ffmpeg_modal.py`
    # Make sure to set your R2 environment variables before running.
    asyncio.run(run_local())
