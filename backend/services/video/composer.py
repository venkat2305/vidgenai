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
from typing import List, Tuple, Dict, Any
from services.video.effects import get_random_effect
import time
from concurrent.futures import ThreadPoolExecutor

executor = ThreadPoolExecutor(max_workers=4)

logger = logging.getLogger("vidgenai.video_composer")

executor = ThreadPoolExecutor(max_workers=4)

async def compose_video(
    script: str,
    image_data: List[Dict[str, Any]],
    audio_path: str,
    subtitle_path: str,
    video_aspect: str = "9:16",
    apply_effects: bool = True
) -> Tuple[str, str, float]:
    """
    Compose a video from images, audio, and subtitles using ffmpeg.
    Returns (video_path, thumbnail_path, duration).
    """
    try:
        temp_dir = tempfile.gettempdir()
        video_filename = os.path.join(
            temp_dir, f"video_{hash(script)}.mp4"
        )
        thumbnail_filename = os.path.join(
            temp_dir, f"thumbnail_{hash(script)}.jpg"
        )

        # Step 1: Parse video dimensions from aspect ratio
        t1_start = time.perf_counter()
        video_dimensions = get_video_dimensions(video_aspect)
        video_width, video_height = video_dimensions
        t1_end = time.perf_counter()
        logger.info(
            f"Step 1: Parsed video dimensions {video_width}x{video_height} "
            f"for aspect {video_aspect} in {t1_end - t1_start:.2f}s"
        )

        # Step 2: Download images and prepare them for the aspect ratio
        t2_start = time.perf_counter()
        image_urls = [img["url"] for img in image_data] if isinstance(image_data[0], dict) else image_data

        unique_image_urls = []
        for url in image_urls:
            if url not in unique_image_urls:
                unique_image_urls.append(url)

        if len(unique_image_urls) < min(5, len(image_urls) // 2):
            logger.warning(
                f"Not enough unique images ({len(unique_image_urls)}). "
                "Will use some duplicates non-consecutively."
            )
            image_urls_arranged = arrange_images_without_consecutive_duplicates(image_urls)
        else:
            image_urls_arranged = arrange_images_without_consecutive_duplicates(unique_image_urls)
            if len(image_urls_arranged) < 8:
                while len(image_urls_arranged) < 8 and len(image_urls_arranged) < len(image_urls):
                    for url in unique_image_urls:
                        if len(image_urls_arranged) >= 8:
                            break
                        if image_urls_arranged[-1] != url:
                            image_urls_arranged.append(url)

        logger.info(f"Using {len(image_urls_arranged)} images after duplicate handling")
        t2_end = time.perf_counter()
        logger.info(f"Step 2: Arranged image URLs in {t2_end - t2_start:.2f}s")

        # Step 3: Download images
        t3_start = time.perf_counter()
        image_paths = await download_images(image_urls_arranged)
        if not image_paths:
            raise Exception("No valid images downloaded")
        t3_end = time.perf_counter()
        logger.info(f"Step 3: Downloaded images in {t3_end - t3_start:.2f}s")

        # Step 4: Pre-process images to fit the target aspect ratio without stretching
        t4_start = time.perf_counter()
        processed_paths = await process_images_for_aspect_ratio(
            image_paths, video_width, video_height
        )
        if not processed_paths:
            raise Exception("Image processing failed")
        t4_end = time.perf_counter()
        logger.info(f"Step 4: Processed images for aspect ratio in {t4_end - t4_start:.2f}s")

        # Step 5: Probe audio duration
        t5_start = time.perf_counter()
        total_duration = await get_media_duration(audio_path)
        t5_end = time.perf_counter()
        logger.info(f"Step 5: Probed audio duration in {t5_end - t5_start:.2f}s")

        # Step 6: Compute per-image durations using equal distribution
        t6_start = time.perf_counter()
        per = total_duration / len(processed_paths)
        durations = [per] * len(processed_paths)
        durations[-1] = total_duration - sum(durations[:-1])
        t6_end = time.perf_counter()
        logger.info(f"Step 6: Computed per-image durations in {t6_end - t6_start:.2f}s")

        # Step 7: Apply effects to create dynamic sequences if requested
        t7_start = time.perf_counter()
        if apply_effects:
            processed_paths = await apply_visual_effects(
                processed_paths, durations, video_width, video_height
            )
        t7_end = time.perf_counter()
        logger.info(f"Step 7: Applied effects in {t7_end - t7_start:.2f}s")

        # Step 8: Build ffmpeg concat list and generate video
        t8_start = time.perf_counter()
        concat_path = os.path.join(
            temp_dir, f"concat_{hash(script)}.txt"
        )

        if apply_effects:
            with open(concat_path, "w", encoding="utf-8") as f:
                for clip_path in processed_paths:
                    f.write(f"file '{clip_path}'\n")
            await generate_final_video_from_clips(
                concat_path, audio_path, subtitle_path,
                video_width, video_height, video_filename
            )
        else:
            with open(concat_path, "w", encoding="utf-8") as f:
                for img, dur in zip(processed_paths, durations):
                    f.write(f"file '{img}'\n")
                    f.write(f"duration {dur}\n")
                f.write(f"file '{processed_paths[-1]}'\n")
            await generate_final_video(
                concat_path, audio_path, subtitle_path,
                video_width, video_height, video_filename
            )
        t8_end = time.perf_counter()
        logger.info(f"Step 8: Generated video in {t8_end - t8_start:.2f}s")

        # Step 9: Make thumbnail from first image
        t9_start = time.perf_counter()
        if isinstance(processed_paths[0], str) and processed_paths[0].endswith(('.jpg', '.png', '.jpeg')):
            shutil.copy(processed_paths[0], thumbnail_filename)
        else:
            cap = cv2.VideoCapture(processed_paths[0])
            ret, frame = cap.read()
            if ret:
                cv2.imwrite(thumbnail_filename, frame)
                cap.release()
            else:
                blank = np.zeros((video_height, video_width, 3), dtype=np.uint8)
                cv2.putText(
                    blank, "No Thumbnail", (video_width // 4, video_height // 2),
                    cv2.FONT_HERSHEY_SIMPLEX, 1,
                    (255, 255, 255), 2
                )
                cv2.imwrite(thumbnail_filename, blank)
        t9_end = time.perf_counter()
        logger.info(f"Step 9: Created thumbnail in {t9_end - t9_start:.2f}s")

        logger.info(f"Video composition complete: {video_filename}")
        return video_filename, thumbnail_filename, total_duration

    except Exception as e:
        logger.error(f"Error composing video: {e}", exc_info=True)
        raise Exception(f"Failed to compose video: {e}")


def arrange_images_without_consecutive_duplicates(image_urls: List[str]) -> List[str]:
  """
  Arrange images so that duplicate images are not consecutive.
  
  Args:
      image_urls: List of image URLs that may contain duplicates
      
  Returns:
      List of image URLs arranged to avoid consecutive duplicates
  """
  if len(image_urls) <= 1:
    return image_urls
    
  # Count occurrences of each image URL
  from collections import Counter
  url_counts = Counter(image_urls)
  
  # Get unique URLs sorted by frequency (most common first for better distribution)
  unique_urls = sorted(url_counts.keys(), key=lambda x: -url_counts[x])
  
  result = []
  last_url = None
  
  # First pass - try to use each URL according to its frequency
  remaining = {url: count for url, count in url_counts.items()}
  
  while sum(remaining.values()) > 0:
    # Find next available URL that's not the same as the last one
    next_url = None
    for url in list(unique_urls):  # Create a copy of the list to avoid modification during iteration
      if url in remaining and remaining[url] > 0 and url != last_url:
        next_url = url
        break
    
    # If we couldn't find a non-consecutive URL, but we still have URLs left,
    # we need to insert a buffer URL and come back to this one
    if next_url is None and remaining:
      # If we have no choice, reuse the last URL
      if len(remaining) == 1:
        next_url = list(remaining.keys())[0]
      else:
        # Find a URL with the fewest occurrences left to use as a buffer
        buffer_urls = [u for u in unique_urls if u in remaining and u != last_url and remaining[u] > 0]
        if buffer_urls:
          next_url = min(buffer_urls, key=lambda x: remaining[x])
    
    if next_url:
      result.append(next_url)
      remaining[next_url] -= 1
      if remaining[next_url] == 0:
        del remaining[next_url]
      last_url = next_url
  
  logger.info(f"Arranged {len(image_urls)} images into {len(result)} positions to avoid consecutive duplicates")
  return result


async def apply_visual_effects(image_paths: List[str], durations: List[float], width: int, height: int) -> List[str]:
    loop = asyncio.get_event_loop()
    tasks = [
        loop.run_in_executor(executor, apply_effect_to_image, i, img_path, duration, width, height)
        for i, (img_path, duration) in enumerate(zip(image_paths, durations))
    ]
    return await asyncio.gather(*tasks)


def apply_effect_to_image(index: int, img_path: str, duration: float, width: int, height: int) -> str:
    temp_dir = tempfile.gettempdir()
    output_video = os.path.join(temp_dir, f"effect_segment_{index}.mp4")
    fps = 30
    effect = get_random_effect()

    try:
        img = cv2.imread(img_path)
        if img is None:
            logger.warning(f"Could not read image {img_path}. Using static image.")
            return img_path

        frame_count = max(1, int(fps * duration))
        frames_dir = os.path.join(temp_dir, f"frames_{index}")
        os.makedirs(frames_dir, exist_ok=True)

        for frame_idx in range(frame_count):
            t = frame_idx / fps
            frame = effect.apply(img.copy(), t, duration)
            frame_path = os.path.join(frames_dir, f"frame_{frame_idx:04d}.jpg")
            cv2.imwrite(frame_path, frame)

        frames_pattern = os.path.join(frames_dir, "frame_%04d.jpg")
        cmd = [
            "ffmpeg", "-y",
            "-framerate", str(fps),
            "-i", frames_pattern,
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-preset", "ultrafast",
            "-crf", "34",
            "-r", str(fps),
            output_video
        ]

        asyncio.run(run_ffmpeg(cmd))
        shutil.rmtree(frames_dir)
        return output_video

    except Exception as e:
        logger.error(f"Error applying effect to image {index}: {e}")
        return img_path


# async def apply_visual_effects(image_paths: List[str], durations: List[float], width: int, height: int) -> List[str]:
#     """
#     Apply visual effects to each image and convert them to short video segments.
#     Returns a list of video segment paths.
#     """
#     temp_dir = tempfile.gettempdir()
#     video_segments = []
#     fps = 30  # frames per second for smooth effects
    
#     # Determine if this is a vertical video (9:16 aspect ratio)
#     is_vertical = height > width

#     for i, (img_path, duration) in enumerate(zip(image_paths, durations)):
#         # Only use zoom effects for vertical videos, as pan effects don't work well in 9:16
#         effect = get_random_effect()  # Now only returns zoom effects
#         logger.info(f"Applying {effect.__class__.__name__} to image {i}")
        
#         # Create output path for this segment
#         output_video = os.path.join(temp_dir, f"effect_segment_{i}.mp4")

#         try:
#             # Read the image
#             img = cv2.imread(img_path)
#             if img is None:
#                 logger.warning(f"Could not read image {img_path}. Using static image.")
#                 video_segments.append(img_path)
#                 continue

#             # Calculate frame count
#             frame_count = int(fps * duration)
#             if frame_count < 1:
#                 frame_count = 1

#             # Create temporary frames directory
#             frames_dir = os.path.join(temp_dir, f"frames_{i}")
#             os.makedirs(frames_dir, exist_ok=True)

#             # Generate frames with applied effect
#             for frame_idx in range(frame_count):
#                 t = frame_idx / fps
#                 frame = effect.apply(img.copy(), t, duration)
#                 frame_path = os.path.join(frames_dir, f"frame_{frame_idx:04d}.jpg")
#                 cv2.imwrite(frame_path, frame)

#             # Combine frames into a video segment
#             frames_pattern = os.path.join(frames_dir, "frame_%04d.jpg")
#             cmd = [
#                 "ffmpeg", "-y",
#                 "-framerate", str(fps),
#                 "-i", frames_pattern,
#                 "-c:v", "libx264",
#                 "-pix_fmt", "yuv420p",
#                 "-preset", "fast",
#                 "-crf", "28",
#                 "-r", str(fps),
#                 output_video
#             ]

#             await run_ffmpeg(cmd)
#             video_segments.append(output_video)

#             # Clean up frames
#             shutil.rmtree(frames_dir)

#         except Exception as e:
#             logger.error(f"Error applying effect to image {i}: {e}")
#             # Fall back to static image
#             video_segments.append(img_path)
    
#     return video_segments


async def generate_final_video_from_clips(concat_path, audio_path, subtitle_path, width, height, output_path):
    """Generate the final video from pre-rendered clips with audio and subtitles."""
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
        "-preset", "ultrafast",
        "-crf", "35",
        "-tune", "zerolatency",
        "-b:v", "400k", 
        "-c:a", "aac",
        "-b:a", "32k",
        "-vf", vf_filters,
        "-shortest",
        output_path
    ]
    
    await run_ffmpeg(cmd)


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
        "-preset", "ultrafast",
        "-b:v", "800k", 
        "-c:a", "aac",
        "-b:a", "64k",
        "-vf", vf_filters,
        "-shortest",
        output_path
    ]
    
    await run_ffmpeg(cmd)


def get_video_dimensions(aspect_ratio: str) -> Tuple[int, int]:
    if aspect_ratio == "9:16":
        return 480, 854
    elif aspect_ratio == "16:9":
        return 854, 480
    elif aspect_ratio == "1:1":
        return 480, 480
    else:
        return 480, 854


async def fetch_image(session, url, path, sem):
    async with sem:
        try:
            async with session.get(url) as resp:
                if resp.status == 200:
                    async with aiofiles.open(path, "wb") as f:
                        await f.write(await resp.read())
                    return path
                else:
                    logger.warning(f"Failed to download {url}: {resp.status}")
        except Exception as e:
            logger.error(f"Error downloading {url}: {e}")
    return None

async def download_images(image_urls: List[str]) -> List[str]:
    temp_dir = tempfile.gettempdir()
    paths: List[str] = []
    sem = asyncio.Semaphore(4)  # Control max concurrency

    async with aiohttp.ClientSession() as session:
        tasks = [
            fetch_image(session, url, os.path.join(temp_dir, f"image_{i}_{hash(url)}.jpg"), sem)
            for i, url in enumerate(image_urls)
        ]
        results = await asyncio.gather(*tasks)
    return [r for r in results if r]


# async def download_images(image_urls: List[str]) -> List[str]:
#   """
#   Download images from URLs.
#   """
  
#   temp_dir = tempfile.gettempdir()
#   paths: List[str] = []

#   async with aiohttp.ClientSession() as session:
#     for i, url in enumerate(image_urls):
#       img_path = os.path.join(temp_dir, f"image_{i}_{hash(url)}.jpg")
#       try:
#         async with session.get(url) as resp:
#           if resp.status == 200:
#             async with aiofiles.open(img_path, "wb") as f:
#               await f.write(await resp.read())
#             paths.append(img_path)
#           else:
#             logger.warning(f"Failed to download {url}: {resp.status}")
#       except Exception as e:
#         logger.error(f"Error downloading {url}: {e}")
#   return paths


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
  cmd = cmd + ["-nostats", "-progress", "pipe:1"]
  proc = await asyncio.create_subprocess_exec(
    *cmd,
    stdout=asyncio.subprocess.PIPE,
    stderr=asyncio.subprocess.PIPE
  )

  # Read ffmpeg's progress lines in real time
  while True:
    line = await proc.stdout.readline()
    if not line:
      break
    text = line.decode().strip()
    print(f"[FFMPEG] {text}")          # ← prints every progress line

  out, err = await proc.communicate()
  if proc.returncode != 0:
    raise Exception(
      f"ffmpeg failed ({proc.returncode}): {err.decode().strip()}"
    )
  return out, err
