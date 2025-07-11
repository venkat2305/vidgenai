import modal
import os
import boto3
from botocore.exceptions import ClientError
from typing import List, Tuple, Dict, Any, Optional
import tempfile
import logging
import asyncio
import aiohttp
import aiofiles
import shutil
import numpy as np
import cv2
from datetime import datetime
import random


# ---- 1. Build an image with all necessary dependencies ----
image = (
    modal.Image.debian_slim()
    .apt_install("ffmpeg")
    .pip_install(
        "boto3",
        "opencv-python-headless",
        "numpy",
        "aiohttp",
        "aiofiles",
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
    R2_ENDPOINT_URL = (
        "https://19614bd5a1eee4fc6adc1abfe9a99795.r2.cloudflarestorage.com"
    )
    R2_PUBLIC_URL_BASE = "https://pub-be0c2eb5ab24406292572a49239fd150.r2.dev"

    try:
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

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


# ---- 3. Video Effects Logic (from effects.py) ----
class VideoEffect:
    def apply(self, frame, t, duration):
        return frame


class ZoomEffect(VideoEffect):
    def __init__(self, zoom_start: float = 1.0, zoom_end: float = 1.2):
        self.zoom_start = zoom_start
        self.zoom_end = zoom_end

    def apply(self, frame, t, duration):
        h, w = frame.shape[:2]
        zoom_factor = (
            self.zoom_start + (self.zoom_end - self.zoom_start) * (t / duration)
        )
        new_h, new_w = int(h * zoom_factor), int(w * zoom_factor)
        y1, x1 = max(0, (new_h - h) // 2), max(0, (new_w - w) // 2)
        y2, x2 = y1 + h, x1 + w
        resized = cv2.resize(
            frame, (new_w, new_h), interpolation=cv2.INTER_LINEAR
        )
        if zoom_factor >= 1.0:
            result = resized[y1:y2, x1:x2]
            return cv2.resize(result, (w, h), interpolation=cv2.INTER_LINEAR)
        else:
            result = np.zeros_like(frame)
            y_offset = (h - new_h) // 2
            x_offset = (w - new_w) // 2
            result[y_offset:y_offset+new_h, x_offset:x_offset+new_w] = resized
            return result


def get_random_effect() -> VideoEffect:
    effects = [
        {"start": 1.0, "end": 1.2},  # Zoom in
        {"start": 1.15, "end": 1.0},  # Zoom out
    ]
    zoom = random.choice(effects)
    return ZoomEffect(zoom["start"], zoom["end"])


# ---- 4. Video Composition Logic (from composer.py) ----
async def compose_video(
    script: str,
    image_data: List[str],  # Changed from List[Dict[str, Any]] to List[str]
    audio_path: str,
    subtitle_path: str,
    video_aspect: str = "9:16",
    apply_effects: bool = True,
    temp_dir: Optional[str] = None,
) -> Tuple[str, str, float]:
    temp_dir = temp_dir or tempfile.gettempdir()
    video_filename = os.path.join(temp_dir, f"video_{hash(script)}.mp4")
    thumbnail_filename = os.path.join(
        temp_dir, f"thumbnail_{hash(script)}.jpg"
    )

    video_width, video_height = get_video_dimensions(video_aspect)

    # Since image_data is now List[str], we can use it directly
    image_urls = image_data
    unique_urls = sorted(list(set(image_urls)))
    image_paths = await download_images(unique_urls, temp_dir)

    if not image_paths:
        raise Exception("No valid images were downloaded.")

    processed_paths = await process_images_for_aspect_ratio(
        image_paths, video_width, video_height, temp_dir
    )
    total_duration = await get_media_duration(audio_path)
    durations = [total_duration / len(processed_paths)] * len(processed_paths)

    if apply_effects:
        processed_paths = await apply_visual_effects(
            processed_paths, durations, video_width, video_height, temp_dir
        )

    concat_path = os.path.join(temp_dir, f"concat_{hash(script)}.txt")
    with open(concat_path, "w", encoding="utf-8") as f:
        if apply_effects:
            for clip_path in processed_paths:
                f.write(f"file '{os.path.basename(clip_path)}'\n")
        else:
            for img, dur in zip(processed_paths, durations):
                f.write(f"file '{os.path.basename(img)}'\n")
                f.write(f"duration {dur}\n")
            f.write(f"file '{os.path.basename(processed_paths[-1])}'\n")

    video_cmd_args = {
        "concat_path": concat_path,
        "audio_path": audio_path,
        "subtitle_path": subtitle_path,
        "width": video_width,
        "height": video_height,
        "output_path": video_filename,
    }

    if apply_effects:
        await generate_final_video_from_clips(**video_cmd_args)
    else:
        await generate_final_video(**video_cmd_args)

    first_frame_source = processed_paths[0]
    if first_frame_source.endswith(('.jpg', '.png', '.jpeg')):
        shutil.copy(first_frame_source, thumbnail_filename)
    else:
        cap = cv2.VideoCapture(first_frame_source)
        ret, frame = cap.read()
        if ret:
            cv2.imwrite(thumbnail_filename, frame)
        cap.release()

    return video_filename, thumbnail_filename, total_duration


async def apply_visual_effects(
    image_paths: List[str], 
    durations: List[float], 
    width: int, 
    height: int, 
    temp_dir: str
) -> List[str]:
    # Process effects sequentially instead of using ThreadPoolExecutor
    processed_paths = []
    for i, (img_path, duration) in enumerate(zip(image_paths, durations)):
        result_path = await apply_effect_to_image(
            i, img_path, duration, width, height, temp_dir
        )
        processed_paths.append(result_path)
    return processed_paths


async def apply_effect_to_image(
    index: int, 
    img_path: str, 
    duration: float, 
    width: int, 
    height: int, 
    temp_dir: str
) -> str:
    output_video = os.path.join(temp_dir, f"effect_segment_{index}.mp4")
    effect = get_random_effect()
    img = cv2.imread(img_path)
    if img is None:
        return img_path
    
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(output_video, fourcc, 30, (width, height))
    
    frame_count = max(1, int(30 * duration))
    for i in range(frame_count):
        t = i / 30
        frame = effect.apply(img.copy(), t, duration)
        out.write(frame)
    out.release()
    return output_video


async def generate_final_video_from_clips(
    concat_path, audio_path, subtitle_path, width, height, output_path
):
    vf_filters = f"subtitles='{subtitle_path}'"
    cmd = [
        "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", concat_path,
        "-i", audio_path, "-map", "0:v", "-map", "1:a", "-c:v", "libx264",
        "-pix_fmt", "yuv420p", "-preset", "ultrafast", "-crf", "35",
        "-c:a", "aac", "-b:a", "32k", "-vf", vf_filters, "-shortest", 
        output_path
    ]
    await run_ffmpeg(cmd)


async def process_images_for_aspect_ratio(
    images: List[str], 
    target_width: int, 
    target_height: int, 
    temp_dir: str
) -> List[str]:
    processed_paths = []
    for i, img_path in enumerate(images):
        output_path = os.path.join(
            temp_dir, f"processed_{i}_{os.path.basename(img_path)}"
        )
        try:
            img = cv2.imread(img_path)
            if img is None:
                continue
            
            img_h, img_w = img.shape[:2]
            target_aspect = target_width / target_height
            img_aspect = img_w / img_h
            
            canvas = np.zeros((target_height, target_width, 3), dtype=np.uint8)
            
            if abs(img_aspect - target_aspect) < 0.1:
                resized = cv2.resize(
                    img, 
                    (target_width, target_height), 
                    interpolation=cv2.INTER_LANCZOS4
                )
                canvas = resized
            elif img_aspect > target_aspect:
                new_w = int(target_height * img_aspect)
                resized = cv2.resize(
                    img, 
                    (new_w, target_height), 
                    interpolation=cv2.INTER_LANCZOS4
                )
                start_x = (new_w - target_width) // 2
                canvas = resized[:, start_x:start_x+target_width]
            else:
                new_h = int(target_width / img_aspect)
                resized = cv2.resize(
                    img, 
                    (target_width, new_h), 
                    interpolation=cv2.INTER_LANCZOS4
                )
                start_y = (target_height - new_h) // 2
                canvas[start_y:start_y+new_h, :] = resized
            
            cv2.imwrite(output_path, canvas)
            processed_paths.append(output_path)
        except Exception as e:
            logger.error(f"Error processing image {img_path}: {e}")
            shutil.copy(img_path, output_path)
            processed_paths.append(output_path)
    return processed_paths


async def generate_final_video(
    concat_path, audio_path, subtitle_path, width, height, output_path
):
    vf_filters = f"subtitles='{subtitle_path}'"
    cmd = [
        "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", concat_path,
        "-i", audio_path, "-map", "0:v", "-map", "1:a", "-c:v", "libx264",
        "-pix_fmt", "yuv420p", "-preset", "ultrafast", "-b:v", "800k",
        "-c:a", "aac", "-b:a", "64k", "-vf", vf_filters, "-shortest", 
        output_path
    ]
    await run_ffmpeg(cmd)


def get_video_dimensions(aspect_ratio: str) -> Tuple[int, int]:
    if aspect_ratio == "9:16":
        return (480, 854)
    elif aspect_ratio == "16:9":
        return (854, 480)
    else:
        return (480, 480)


async def fetch_file(session, url, path, sem):
    async with sem:
        try:
            async with session.get(url) as resp:
                if resp.status == 200:
                    async with aiofiles.open(path, "wb") as f:
                        await f.write(await resp.read())
                    return path
        except Exception as e:
            logger.error(f"Failed to download {url}: {e}")
    return None


async def download_images(image_urls: List[str], temp_dir: str) -> List[str]:
    sem = asyncio.Semaphore(10)
    async with aiohttp.ClientSession() as session:
        tasks = [
            fetch_file(
                session, 
                url, 
                os.path.join(temp_dir, f"image_{i}.jpg"), 
                sem
            )
            for i, url in enumerate(image_urls)
        ]
        results = await asyncio.gather(*tasks)
    return [r for r in results if r]


async def get_media_duration(path: str) -> float:
    cmd = [
        "ffprobe", "-v", "error", "-show_entries", "format=duration", 
        "-of", "default=noprint_wrappers=1:nokey=1", path
    ]
    proc = await asyncio.create_subprocess_exec(
        *cmd, 
        stdout=asyncio.subprocess.PIPE, 
        stderr=asyncio.subprocess.PIPE
    )
    out, err = await proc.communicate()
    if proc.returncode != 0:
        raise Exception(f"ffprobe failed: {err.decode()}")
    return float(out.decode().strip())


async def run_ffmpeg(cmd: List[str]):
    proc = await asyncio.create_subprocess_exec(
        *cmd, 
        stdout=asyncio.subprocess.PIPE, 
        stderr=asyncio.subprocess.PIPE
    )
    _, err = await proc.communicate()
    if proc.returncode != 0:
        raise Exception(
            f"ffmpeg failed with exit code {proc.returncode}: {err.decode()}"
        )


# ---- 5. Main Modal Function ----
@app.function(
    cpu=4,
    memory=1024,
    retries=1,
    secrets=[modal.Secret.from_name("r2-credentials")],
    timeout=900,
    scaledown_window=200,
)
async def generate_video(
    image_urls: List[str],
    audio_url: str,
    subtitle_url: str,
    script: str,
    video_aspect: str = "9:16",
    apply_effects: bool = True,
):
    with tempfile.TemporaryDirectory() as temp_dir:
        # Change working dir for simplicity with ffmpeg concat files
        os.chdir(temp_dir)

        # Download audio and subtitles
        async with aiohttp.ClientSession() as session:
            audio_path = await fetch_file(
                session, audio_url, "audio.mp3", asyncio.Semaphore(1)
            )
            subtitle_path = await fetch_file(
                session, subtitle_url, "subtitles.srt", asyncio.Semaphore(1)
            )

        if not audio_path:
            raise Exception("Failed to download audio.")
        if not subtitle_path:
            raise Exception("Failed to download subtitles.")

        # Create video
        video_path, thumb_path, _ = await compose_video(
            script, image_urls, audio_path, subtitle_path, 
            video_aspect, apply_effects, temp_dir
        )

        # Upload to R2
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        video_key = f"{timestamp}_{os.path.basename(video_path)}"
        thumb_key = f"{timestamp}_{os.path.basename(thumb_path)}"

        video_url = await upload_to_r2(video_path, video_key)
        thumb_url = await upload_to_r2(thumb_path, thumb_key)

        return {
            "success": True,
            "video_url": video_url,
            "thumbnail_url": thumb_url,
        }


# ---- 6. Local entry-point for testing ----
@app.local_entrypoint()
async def main():
    # This is a test function. Replace with actual data.
    # Existing async test harness
    test_image_urls = [
        "https://www.sportphotogallery.com/content/images/cmsfiles/"
        "product/24678/24947-list.jpg",
        "https://media.gettyimages.com/id/1076435316/photo/"
        "adelaide-australia-virat-kohli-of-india-poses-during-the-india-"
        "test-squad-portrait-session-on.jpg?s=612x612&w=0&k=20&c="
        "RrgJMrI-5D4fvi5w8w8t4Lt42y2cy2T9Mb8k6fFmrTs=",
        "https://media.gettyimages.com/id/1495889200/photo/"
        "london-england-virat-kohli-of-india-poses-for-a-portrait-"
        "prior-to-the-icc-world-test.jpg?s=612x612&w=0&k=20&c="
        "SbcF6ggb7Zd5bA_bSyOsUc0xnYlG9qSgaZrXC0gFkQE=",
        "https://c.ndtvimg.com/2023-03/"
        "hqotnscg_virat-kohli_625x300_26_March_23.jpg?downsize=773:435",
        "https://media.gettyimages.com/id/1495889131/photo/"
        "london-england-virat-kohli-of-india-poses-for-a-portrait-"
        "prior-to-the-icc-world-test.jpg?s=612x612&w=0&k=20&c="
        "6Oc03AHKNf9JefLvY1Atb6UJVKWvdNwgs46ZaDIN6Mg=",
        "https://img1.hscicdn.com/image/upload/f_auto,t_ds_w_1280,q_80/"
        "lsci/db/PICTURES/CMS/289000/289002.jpg",
        "https://media.gettyimages.com/id/1151434004/photo/"
        "london-england-virat-kohli-of-india-poses-for-a-portrait-"
        "prior-to-the-icc-cricket-world-cup.jpg?s=612x612&w=0&k=20&c="
        "W7wCkhX3gk1tpYJOan6geJBPU8FIJgC0xme5phwPFYo=",
        "https://media.gettyimages.com/id/1076452406/photo/"
        "adelaide-australia-virat-kohli-of-india-poses-during-the-india-"
        "test-squad-portrait-session-on.jpg?s=612x612&w=0&k=20&c="
        "G3RyNFeBhksZzNMIjlTJMNPCUgpDtFwa8cc5bUG0wms="
    ]

    test_audio_url = (
        "https://pub-be0c2eb5ab24406292572a49239fd150.r2.dev/"
        "3cc75fd2-ffef-4d95-9d69-3b6d86c07ddf.mp3"
    )

    # Use the provided subtitle URL
    test_subtitle_url = (
        "https://pub-be0c2eb5ab24406292572a49239fd150.r2.dev/"
        "3cc75fd2-ffef-4d95-9d69-3b6d86c07ddf.srt"
    )

    test_script = (
        "Virat Kohli, the Indian cricket sensation, made history by "
        "becoming the first player to score20,000 runs in a decade. "
        "Known as the Cricketer of the Decade from2011 to2020, Kohli's "
        "achievements are a testament to his dedication and skill. He "
        "holds the record for most ODI centuries with50, surpassing "
        "Sachin Tendulkar. In Test cricket, Kohli captained India to "
        "their first-ever series win in Australia and led the team to "
        "the top of the ICC rankings for five consecutive years. As "
        "Kohli once said, \"You don't have to be great to start, but "
        "you have to start to be great.\" His legacy continues to "
        "inspire generations of cricketers, cementing his place as one "
        "of the greatest batsmen in the sport's history."
    )

    print("Running test generation...")
    try:
        result = await generate_video.remote.aio(
            image_urls=test_image_urls,
            audio_url=test_audio_url,
            subtitle_url=test_subtitle_url,
            script=test_script,
        )
        print(f"Test Result: {result}")
    except Exception as exc:
        print(f"Test failed: {exc}")
        print(
            "Please ensure you have valid 'r2-credentials' in Modal and that "
            "the audio URL is publicly accessible."
        )
