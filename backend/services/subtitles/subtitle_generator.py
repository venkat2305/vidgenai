import os
import tempfile
import logging
import json
import re
from typing import List, Tuple
import whisper
import asyncio

logger = logging.getLogger("vidgenai.subtitle_generator")


async def generate_subtitles(script: str, audio_path: str) -> str:
    """
    Generate styled subtitles from script and audio.
    
    Args:
        script: The script text
        audio_path: Path to the audio file
        
    Returns:
        Path to the generated subtitle file
    """
    try:
        # Create a temporary file for the subtitles
        temp_dir = tempfile.gettempdir()
        subtitle_filename = os.path.join(temp_dir, f"subtitles_{os.path.basename(audio_path)}.srt")
        
        # Use whisper to transcribe audio with timestamps
        logger.info(f"Transcribing audio with whisper: {audio_path}")
        
        # Run whisper in a separate thread to avoid blocking
        model = await asyncio.to_thread(whisper.load_model, "base")
        result = await asyncio.to_thread(model.transcribe, audio_path, fp16=False)
        
        # Generate SRT format subtitles
        with open(subtitle_filename, "w", encoding="utf-8") as f:
            for i, segment in enumerate(result["segments"], 1):
                start_time = format_timestamp(segment["start"])
                end_time = format_timestamp(segment["end"])
                text = segment["text"].strip()
                
                f.write(f"{i}\n")
                f.write(f"{start_time} --> {end_time}\n")
                f.write(f"{text}\n\n")
        
        logger.info(f"Generated subtitle file: {subtitle_filename}")
        return subtitle_filename
        
    except Exception as e:
        logger.error(f"Error generating subtitles: {str(e)}", exc_info=True)
        
        # Fallback to simple time-based subtitle generation if whisper fails
        try:
            logger.info("Falling back to simple subtitle generation")
            return await generate_simple_subtitles(script, subtitle_filename)
        except Exception as fallback_error:
            logger.error(f"Fallback subtitle generation failed: {str(fallback_error)}", exc_info=True)
            raise Exception(f"Failed to generate subtitles: {str(e)}")

async def generate_simple_subtitles(script: str, output_path: str) -> str:
    """
    Generate simple time-based subtitles without audio analysis.
    
    This is a fallback method if whisper transcription fails.
    """
    # Split script into sentences
    sentences = re.split(r'(?<=[.!?]) +', script)
    sentences = [s.strip() for s in sentences if s.strip()]
    
    # Estimate average reading speed (chars per second)
    chars_per_second = 15
    
    # Generate subtitles with estimated timing
    with open(output_path, "w", encoding="utf-8") as f:
        current_time = 0
        
        for i, sentence in enumerate(sentences, 1):
            # Estimate duration based on character count
            duration = max(1.5, len(sentence) / chars_per_second)
            
            start_time = format_timestamp(current_time)
            end_time = format_timestamp(current_time + duration)
            
            f.write(f"{i}\n")
            f.write(f"{start_time} --> {end_time}\n")
            f.write(f"{sentence}\n\n")
            
            current_time += duration
    
    logger.info(f"Generated simple subtitle file: {output_path}")
    return output_path

def format_timestamp(seconds: float) -> str:
    """
    Format seconds into SRT timestamp format (HH:MM:SS,mmm).
    """
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    seconds = seconds % 60
    milliseconds = int((seconds - int(seconds)) * 1000)
    
    return f"{hours:02d}:{minutes:02d}:{int(seconds):02d},{milliseconds:03d}"
