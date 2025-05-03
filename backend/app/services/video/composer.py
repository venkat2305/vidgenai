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
from typing import List, Tuple

logger = logging.getLogger("vidgenai.video_composer")


async def compose_video(
  script: str,
  image_urls: List[str],
  audio_path: str,
  subtitle_path: str
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

    # 1) Download images
    image_paths = await download_images(image_urls)
    if not image_paths:
      raise Exception("No valid images downloaded")

    # 2) Probe audio duration
    total_duration = await get_media_duration(audio_path)

    # 3) Compute per-image durations
    per = total_duration / len(image_paths)
    durations = [per] * len(image_paths)
    # adjust last slice to hit exact total
    durations[-1] = total_duration - sum(durations[:-1])

    # 4) Build ffmpeg concat list
    concat_path = os.path.join(
      temp_dir, f"concat_{hash(script)}.txt"
    )
    with open(concat_path, "w", encoding="utf-8") as f:
      for img, dur in zip(image_paths, durations):
        f.write(f"file '{img}'\n")
        f.write(f"duration {dur}\n")
      # repeat last image to ensure its duration is honored
      f.write(f"file '{image_paths[-1]}'\n")

    # 5) Build the filter chain: scale + burn subtitles
    # Simplify subtitles filter: only burn subtitles with default style
    vf_filters = f"scale=1280:720,subtitles={subtitle_path}"
    
    logger.info(f"Using filter chain: {vf_filters}")

    # 6) Invoke ffmpeg
    cmd = [
      "ffmpeg", "-y",
      "-f", "concat",
      "-safe", "0",
      "-i", concat_path,
      "-i", audio_path,
      "-c:v", "libx264",
      "-preset", "medium",
      "-threads", "4",
      "-b:a", "192k",
      "-c:a", "aac",
      "-pix_fmt", "yuv420p",
      "-vf", vf_filters,
      "-shortest",
      video_filename
    ]
    await run_ffmpeg(cmd)

    # 7) Make thumbnail from first image
    if image_paths:
      shutil.copy(image_paths[0], thumbnail_filename)
    else:
      blank = np.zeros((720, 1280, 3), dtype=np.uint8)
      cv2.putText(
        blank, "No Thumbnail", (480, 360),
        cv2.FONT_HERSHEY_SIMPLEX, 1,
        (255, 255, 255), 2
      )
      cv2.imwrite(thumbnail_filename, blank)

    logger.info(f"Video composition complete: {video_filename}")
    return video_filename, thumbnail_filename, total_duration

  except Exception as e:
    logger.error(f"Error composing video: {e}", exc_info=True)
    raise Exception(f"Failed to compose video: {e}")


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



# # flake8: noqa
# import os
# import tempfile
# import logging
# import asyncio
# import aiohttp
# import aiofiles
# import shutil
# import numpy as np
# import cv2
# from typing import List, Tuple

# logger = logging.getLogger("vidgenai.video_composer")


# async def compose_video(
#   script: str,
#   image_urls: List[str],
#   audio_path: str,
#   subtitle_path: str
# ) -> Tuple[str, str, float]:
#   """
#   Compose a video from images, audio, and subtitles using ffmpeg.
#   Returns (video_path, thumbnail_path, duration).
#   """
#   try:
#     temp_dir = tempfile.gettempdir()
#     video_filename = os.path.join(
#       temp_dir, f"video_{hash(script)}.mp4"
#     )
#     thumbnail_filename = os.path.join(
#       temp_dir, f"thumbnail_{hash(script)}.jpg"
#     )

#     # 1) Download images
#     image_paths = await download_images(image_urls)
#     if not image_paths:
#       raise Exception("No valid images downloaded")

#     # 2) Probe audio duration
#     total_duration = await get_media_duration(audio_path)

#     # 3) Compute per-image durations
#     per = total_duration / len(image_paths)
#     durations = [per] * len(image_paths)
#     # adjust last slice to hit exact total
#     durations[-1] = total_duration - sum(durations[:-1])

#     # 4) Build ffmpeg concat list
#     concat_path = os.path.join(
#       temp_dir, f"concat_{hash(script)}.txt"
#     )
#     with open(concat_path, "w", encoding="utf-8") as f:
#       for img, dur in zip(image_paths, durations):
#         f.write(f"file '{img}'\n")
#         f.write(f"duration {dur}\n")
#       # repeat last image to ensure its duration is honored
#       f.write(f"file '{image_paths[-1]}'\n")

#     # 5) Build filter_complex for video only (scale + subtitles)
#     vf_filters = f"scale=1280:720,subtitles={subtitle_path}"
#     filter_complex = f"[0:v]{vf_filters}[v]"
#     logger.info(f"Using filter_complex_video: {filter_complex}")

#     # 6) Generate a video-only temp file with subtitles
#     temp_video = os.path.join(temp_dir, f"video_tmp_{hash(script)}.mp4")
#     cmd_video = [
#       "ffmpeg", "-y",
#       "-loglevel", "info",
#       "-f", "concat",
#       "-safe", "0",
#       "-i", concat_path,
#       "-vf", vf_filters,
#       "-c:v", "libx264",
#       "-preset", "medium",
#       "-threads", "4",
#       "-pix_fmt", "yuv420p",
#       temp_video
#     ]
#     await run_ffmpeg(cmd_video)

#     # 7) Merge the generated video with the audio track
#     cmd_merge = [
#       "ffmpeg", "-y",
#       "-loglevel", "info",
#       "-i", temp_video,
#       "-i", audio_path,
#       # map the video from the first input and audio from the second
#       "-map", "0:v",
#       "-map", "1:a",
#       "-c:v", "copy",
#       "-c:a", "aac",
#       "-b:a", "192k",
#       "-shortest",
#       video_filename
#     ]
#     await run_ffmpeg(cmd_merge)
#     # clean up temp video
#     os.remove(temp_video)

#     # 8) Make thumbnail from first image
#     if image_paths:
#       shutil.copy(image_paths[0], thumbnail_filename)
#     else:
#       blank = np.zeros((720, 1280, 3), dtype=np.uint8)
#       cv2.putText(
#         blank, "No Thumbnail", (480, 360),
#         cv2.FONT_HERSHEY_SIMPLEX, 1,
#         (255, 255, 255), 2
#       )
#       cv2.imwrite(thumbnail_filename, blank)

#     logger.info(f"Video composition complete: {video_filename}")
#     return video_filename, thumbnail_filename, total_duration

#   except Exception as e:
#     logger.error(f"Error composing video: {e}", exc_info=True)
#     raise Exception(f"Failed to compose video: {e}")


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


# async def get_media_duration(path: str) -> float:
#   """
#   Use ffprobe to get media duration in seconds.
#   """
#   cmd = [
#     "ffprobe",
#     "-v", "error",
#     "-show_entries", "format=duration",
#     "-of", "default=noprint_wrappers=1:nokey=1",
#     path
#   ]
#   proc = await asyncio.create_subprocess_exec(
#     *cmd,
#     stdout=asyncio.subprocess.PIPE,
#     stderr=asyncio.subprocess.PIPE
#   )
#   out, err = await proc.communicate()
#   if proc.returncode != 0:
#     raise Exception(f"ffprobe failed: {err.decode().strip()}")
#   return float(out.decode().strip())


# async def run_ffmpeg(cmd: List[str]) -> Tuple[bytes, bytes]:
#   """
#   Run an ffmpeg command asynchronously.
#   """
#   proc = await asyncio.create_subprocess_exec(
#     *cmd,
#     stdout=asyncio.subprocess.PIPE,
#     stderr=asyncio.subprocess.PIPE
#   )
#   out, err = await proc.communicate()
#   if proc.returncode != 0:
#     raise Exception(
#       f"ffmpeg failed ({proc.returncode}): {err.decode().strip()}"
#     )
#   return out, err
