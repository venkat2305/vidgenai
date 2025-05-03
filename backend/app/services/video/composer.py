# flake8: noqa
import os
import tempfile
import logging
import asyncio
import aiohttp
import aiofiles
import shutil
import numpy as np
import cv2
from typing import List, Tuple, Dict, Any, Optional

logger = logging.getLogger("vidgenai.video_composer")


async def compose_video(
  script: str,
  image_data: List[Dict[str, Any]],
  audio_path: str,
  subtitle_path: str,
  video_aspect: str = "9:16"
) -> Tuple[str, str, float]:
  """
  Compose a video from images, audio, and subtitles using ffmpeg.
  Returns (video_path, thumbnail_path, duration).
  
  Args:
    script: The script text
    image_data: List of dictionaries containing image URLs and metadata
    audio_path: Path to the audio file
    subtitle_path: Path to the subtitle file
    video_aspect: Desired video aspect ratio (e.g., "9:16", "16:9")
  """
  try:
    temp_dir = tempfile.gettempdir()
    video_filename = os.path.join(
      temp_dir, f"video_{hash(script)}.mp4"
    )
    thumbnail_filename = os.path.join(
      temp_dir, f"thumbnail_{hash(script)}.jpg"
    )
    
    # Parse video dimensions from aspect ratio
    video_dimensions = get_video_dimensions(video_aspect)
    video_width, video_height = video_dimensions
    logger.info(f"Creating {video_width}x{video_height} video with {video_aspect} aspect ratio")

    # 1) Download images and prepare them for the aspect ratio
    image_urls = [img["url"] for img in image_data] if isinstance(image_data[0], dict) else image_data
    image_paths = await download_images(image_urls)
    if not image_paths:
      raise Exception("No valid images downloaded")
    
    # 2) Pre-process images to fit the target aspect ratio without stretching
    processed_paths = await process_images_for_aspect_ratio(image_paths, video_width, video_height)
    if not processed_paths:
      raise Exception("Image processing failed")

    # 3) Probe audio duration
    total_duration = await get_media_duration(audio_path)

    # 4) Compute per-image durations
    per = total_duration / len(processed_paths)
    durations = [per] * len(processed_paths)
    # adjust last slice to hit exact total
    durations[-1] = total_duration - sum(durations[:-1])

    # 5) Build ffmpeg concat list
    concat_path = os.path.join(
      temp_dir, f"concat_{hash(script)}.txt"
    )
    with open(concat_path, "w", encoding="utf-8") as f:
      for img, dur in zip(processed_paths, durations):
        f.write(f"file '{img}'\n")
        f.write(f"duration {dur}\n")
      # repeat last image to ensure its duration is honored
      f.write(f"file '{processed_paths[-1]}'\n")

    # 6) Generate the video
    await generate_final_video(concat_path, audio_path, subtitle_path, video_width, video_height, video_filename)

    # 7) Make thumbnail from first image
    if processed_paths:
      shutil.copy(processed_paths[0], thumbnail_filename)
    else:
      blank = np.zeros((video_height, video_width, 3), dtype=np.uint8)
      cv2.putText(
        blank, "No Thumbnail", (video_width // 4, video_height // 2),
        cv2.FONT_HERSHEY_SIMPLEX, 1,
        (255, 255, 255), 2
      )
      cv2.imwrite(thumbnail_filename, blank)

    logger.info(f"Video composition complete: {video_filename}")
    return video_filename, thumbnail_filename, total_duration

  except Exception as e:
    logger.error(f"Error composing video: {e}", exc_info=True)
    raise Exception(f"Failed to compose video: {e}")


async def process_images_for_aspect_ratio(images: List[str], target_width: int, target_height: int) -> List[str]:
    """
    Process images to fit the target aspect ratio without stretching.
    For mismatched aspect ratios, will add background padding or crop as appropriate.
    """
    temp_dir = tempfile.gettempdir()
    processed_paths = []
    
    for i, img_path in enumerate(images):
        output_path = os.path.join(temp_dir, f"processed_{i}_{os.path.basename(img_path)}")
        try:
            # Read image
            img = cv2.imread(img_path)
            if img is None:
                logger.warning(f"Could not read image {img_path}. Skipping.")
                continue
                
            img_h, img_w = img.shape[:2]
            img_aspect = img_w / img_h
            target_aspect = target_width / target_height
            
            # Create a blank canvas with the target dimensions
            canvas = np.zeros((target_height, target_width, 3), dtype=np.uint8)
            
            # Fill with a dark gradient background (looks better than solid color)
            for y in range(target_height):
                factor = y / target_height
                color = (int(30 * factor), int(30 * factor), int(30 * factor))
                canvas[y, :] = color
                
            if abs(img_aspect - target_aspect) < 0.1:
                # Similar aspect ratios - resize to fill the canvas
                resized = cv2.resize(img, (target_width, target_height), interpolation=cv2.INTER_LANCZOS4)
                canvas = resized
            elif img_aspect > target_aspect:
                # Image is wider than target - resize to match height and crop width
                new_width = int(target_height * img_aspect)
                resized = cv2.resize(img, (new_width, target_height), interpolation=cv2.INTER_LANCZOS4)
                # Center crop
                start_x = (new_width - target_width) // 2
                canvas = resized[:, start_x:start_x+target_width]
            else:
                # Image is taller than target - resize to match width and fill with background
                new_height = int(target_width / img_aspect)
                resized = cv2.resize(img, (target_width, new_height), interpolation=cv2.INTER_LANCZOS4)
                # Center in canvas
                start_y = (target_height - new_height) // 2
                canvas[start_y:start_y+new_height, :] = resized
            
            cv2.imwrite(output_path, canvas)
            processed_paths.append(output_path)
            
        except Exception as e:
            logger.error(f"Error processing image {img_path}: {e}")
            # If processing fails, try to use the original image
            try:
                shutil.copy(img_path, output_path)
                processed_paths.append(output_path)
            except:
                logger.error(f"Could not copy original image {img_path} as fallback.")
    
    return processed_paths


async def generate_final_video(concat_path, audio_path, subtitle_path, width, height, output_path):
    """Generate the final video with audio and subtitles."""
    # Build filter chain for subtitles
    vf_filters = f"subtitles={subtitle_path}"
    
    # Command to generate the final video
    cmd = [
        "ffmpeg", "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", concat_path,
        "-i", audio_path,
        "-map", "0:v",  # Video from first input
        "-map", "1:a",  # Audio from second input
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-preset", "medium",
        "-b:v", "2500k", 
        "-c:a", "aac",
        "-b:a", "192k",
        "-vf", vf_filters,
        "-shortest",
        output_path
    ]
    
    await run_ffmpeg(cmd)


def get_video_dimensions(aspect_ratio: str) -> Tuple[int, int]:
    """Get video dimensions based on aspect ratio."""
    if aspect_ratio == "9:16":  # Vertical video for shorts/reels
        return 720, 1280  # 720x1280 (9:16)
    elif aspect_ratio == "16:9":  # Standard widescreen
        return 1280, 720  # 1280x720 (16:9)
    elif aspect_ratio == "1:1":  # Square video
        return 1080, 1080  # 1080x1080 (1:1)
    else:
        # Default to 9:16 for short-form vertical video
        return 720, 1280


async def download_images(image_urls: List[str]) -> List[str]:
  """
  Download images from URLs.
  """
  temp_dir = tempfile.gettempdir()
  paths: List[str] = []

  async with aiohttp.ClientSession() as session:
    for i, url in enumerate(image_urls):
      img_path = os.path.join(temp_dir, f"image_{i}_{hash(url)}.jpg")
      try:
        async with session.get(url) as resp:
          if resp.status == 200:
            async with aiofiles.open(img_path, "wb") as f:
              await f.write(await resp.read())
            paths.append(img_path)
          else:
            logger.warning(f"Failed to download {url}: {resp.status}")
      except Exception as e:
        logger.error(f"Error downloading {url}: {e}")
  return paths


async def get_media_duration(path: str) -> float:
  """
  Use ffprobe to get media duration in seconds.
  """
  cmd = [
    "ffprobe",
    "-v", "error",
    "-show_entries", "format=duration",
    "-of", "default=noprint_wrappers=1:nokey=1",
    path
  ]
  proc = await asyncio.create_subprocess_exec(
    *cmd,
    stdout=asyncio.subprocess.PIPE,
    stderr=asyncio.subprocess.PIPE
  )
  out, err = await proc.communicate()
  if proc.returncode != 0:
    raise Exception(f"ffprobe failed: {err.decode().strip()}")
  return float(out.decode().strip())


async def run_ffmpeg(cmd: List[str]) -> Tuple[bytes, bytes]:
  """
  Run an ffmpeg command asynchronously.
  """
  proc = await asyncio.create_subprocess_exec(
    *cmd,
    stdout=asyncio.subprocess.PIPE,
    stderr=asyncio.subprocess.PIPE
  )
  out, err = await proc.communicate()
  if proc.returncode != 0:
    raise Exception(
      f"ffmpeg failed ({proc.returncode}): {err.decode().strip()}"
    )
  return out, err
