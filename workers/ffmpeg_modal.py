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

app = modal.App("video-generator-optimized", image=image)
logger = logging.getLogger("vidgenai.modal_worker")


# ---- 2. R2 Upload Function ----
async def upload_to_r2(file_path: str, object_key: str) -> str:
    # Configuration is loaded from Modal secrets
    R2_ACCESS_KEY_ID = os.environ["R2_ACCESS_KEY_ID"]
    R2_SECRET_ACCESS_KEY = os.environ["R2_SECRET_ACCESS_KEY"]
    R2_BUCKET_NAME = os.environ["R2_BUCKET_NAME"]
    R2_ENDPOINT_URL = (
        "https://19614bd5a1eee4fc6adc1abfe9a99795.r2.cloudflarestorage.com"
    )
    R2_PUBLIC_URL_BASE = "https://pub-be0c2eb5ab24406292572a49239fd150.r2.dev"

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
    
    def _get_video_dimensions(self, aspect_ratio: str) -> Tuple[int, int]:
        dimensions = {
            "9:16": (1080, 1920),  # Increased resolution for better quality
            "16:9": (1920, 1080),
            "1:1": (1080, 1080),
        }
        return dimensions.get(aspect_ratio, (1080, 1920))
    
    def _build_effect_filter(
        self, index: int, duration: float, width: int, height: int, 
        effect_type: str
    ) -> str:
        """Build effect filter for a single image"""
        fps = 30
        frames = int(duration * fps)
        
        # Base scaling and padding
        base_filter = f"""[{index}:v]
        scale={width}:{height}:force_original_aspect_ratio=decrease,
        pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:black"""
        
        # SAR normalization and pixel format fix
        post = f",setsar=1,setdar={width}/{height},format=yuv420p"
        
        # Add effect based on type
        if effect_type == "zoom_in":
            effect = f"""zoompan=z='min(zoom+0.0015,1.3)':
                       d={frames}:s={width}x{height}:fps={fps}"""
        elif effect_type == "zoom_out":
            effect = f"""zoompan=z='if(eq(on,1),1.3,max(1.001,zoom-0.0015))':
                       d={frames}:s={width}x{height}:fps={fps}"""
        elif effect_type == "pan_left":
            effect = f"""zoompan=z='1.2':x='if(gte(on,1),(on-1)*2,0)':
                       d={frames}:s={width}x{height}:fps={fps}"""
        elif effect_type == "pan_right":
            # pan from right edge toward the left by 2 px per frame
            effect = (
                "zoompan="
                "z='1.2':"
                "x='if(gte(on,1),iw-ow-(on-1)*2,iw-ow)':"
                f"d={frames}:s={width}x{height}:fps={fps}"
            )
        else:  # ken_burns - combination
            effect = f"""zoompan=z='min(zoom+0.001,1.2)':
                       x='if(gte(zoom,1.2),x+1,x)':y='if(gte(zoom,1.2),y+1,y)':
                       d={frames}:s={width}x{height}:fps={fps}"""
        
        return f"{base_filter},{effect}{post},setpts=PTS-STARTPTS[v{index}]"
    
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
        apply_effects: bool = True
    ) -> Tuple[str, float]:
        """Generate video in a single FFmpeg pass"""
        
        width, height = self._get_video_dimensions(video_aspect)
        
        # Build FFmpeg command
        cmd = ["ffmpeg", "-y"]
        
        # Add inputs
        filter_parts = []
        for i, (img_path, duration) in enumerate(zip(image_paths, durations)):
            cmd.extend(["-loop", "1", "-t", str(duration), "-i", img_path])
            
            # Build filter for this image
            if apply_effects:
                effect_type = self._get_random_effect()
                filter_parts.append(
                    self._build_effect_filter(
                        i, duration, width, height, effect_type
                    )
                )
            else:
                # Simple scale and pad
                filter_parts.append(f"""[{i}:v]
                    scale={width}:{height}:force_original_aspect_ratio=decrease,
                    pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:black,
                    fps=30,setsar=1,setdar={width}/{height},format=yuv420p,
                    setpts=PTS-STARTPTS[v{i}]""")
        
        # Add audio input
        audio_index = len(image_paths)
        cmd.extend(["-i", audio_path])
        
        # Build concatenation filter
        concat_inputs = "".join([f"[v{i}]" for i in range(len(image_paths))])
        concat_filter = (
            f"{concat_inputs}concat=n={len(image_paths)}:v=1:a=0[outv]"
        )
        
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
        
        # Add filter complex to command
        cmd.extend(["-filter_complex", filter_complex])
        
        # Map outputs
        cmd.extend(["-map", "[final]", "-map", f"{audio_index}:a"])
        
        # CPU-only output settings
        cmd.extend([
            "-c:v", "libx264",
            "-preset", "fast",  # Better than ultrafast
            "-crf", "23",       # Good quality
            "-tune", "film",    # Optimize for video content
        ])
        
        # Audio settings
        cmd.extend([
            "-c:a", "aac",
            "-b:a", "128k",
            "-ar", "44100",
            "-shortest",  # Match video length to shortest input
            output_path
        ])
        
        print("Running FFmpeg command")
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
    apply_effects: bool = True
) -> Dict[str, Any]:
    """Main function to generate video with optimizations"""
    
    with tempfile.TemporaryDirectory() as temp_dir:
        # Change to temp directory for simpler paths
        original_cwd = os.getcwd()
        os.chdir(temp_dir)
        
        try:
            # Download audio and subtitles concurrently
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
            
            print("Downloaded audio and subtitles")
            
            # Get audio duration
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
            
            print("Got audio duration")
            
            # Preprocess images
            image_paths = await preprocess_images(image_urls, temp_dir)
            
            print("Preprocessed images")
            
            # Calculate duration per image
            durations = [total_duration / len(image_paths)] * len(image_paths)
            
            print("Calculated duration per image")
            
            # Generate video using single-pass approach
            generator = SinglePassVideoGenerator()
            video_path = "output.mp4"
            
            print("Generated video using single-pass approach")
            
            _, generation_time = await generator.generate_video(
                image_paths=image_paths,
                durations=durations,
                audio_path=audio_path,
                subtitle_path=subtitle_path,
                output_path=video_path,
                video_aspect=video_aspect,
                apply_effects=apply_effects
            )
            
            print(f"Video generated in {generation_time:.2f} seconds")
            
            logger.info(f"Video generated in {generation_time:.2f} seconds")
            
            # Use the first image as the thumbnail
            thumbnail_path = image_paths[0]
            
            print("Using the first image as thumbnail")
            
            # Upload to R2
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # Use deterministic hash for consistent naming
            script_hash = hashlib.md5(script.encode()).hexdigest()[:8]
            video_key = f"videos/{timestamp}_{script_hash}.mp4"
            thumb_key = f"thumbnails/{timestamp}_{script_hash}.jpg"
            
            video_url = await upload_to_r2(video_path, video_key)
            thumb_url = await upload_to_r2(
                thumbnail_path, thumb_key
            )
            print("Video generated successfully")
            return {
                "success": True,
                "video_url": video_url,
                "thumbnail_url": thumb_url,
                "duration": total_duration,
                "generation_time": generation_time
            }
            
        finally:
            os.chdir(original_cwd)


# ---- 6. Modal Function ----
@app.function(
    cpu=8.0,        # More CPU for CPU-only processing
    memory=4096,    # More memory for CPU processing
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
            apply_effects=apply_effects
        )
        
        logger.info(f"Video generation completed: {result}")
        return result
        
    except Exception as e:
        logger.error(f"Video generation failed: {e}")
        return {
            "success": False,
            "error": str(e)
        }


# ---- 7. Test Entrypoint ----
@app.local_entrypoint()
async def main():
    """Test the optimized video generation"""
    
    from test_data import test_image_urls, test_audio_url, test_subtitle_url, test_script
    
    test_data = {
        "image_urls": test_image_urls,
        "audio_url": test_audio_url,
        "subtitle_url": test_subtitle_url,
        "script": test_script,
        "video_aspect": "9:16",
        "apply_effects": True
    }
    
    print("Testing optimized video generation...")
    
    # Test CPU-only version
    try:
        result = await generate_video.remote.aio(**test_data)
        print(f"CPU Result: {result}")
    except Exception as e:
        print(f"CPU test failed: {e}")
