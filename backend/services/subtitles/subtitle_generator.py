import os
import tempfile
import logging
import json
import re
import httpx
from typing import List, Tuple, Dict, Any
import whisper
import asyncio
from core.config import settings

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
        
        # Correct the transcription using the original script with Groq API
        corrected_segments = await correct_transcription_with_groq(result["segments"], script)
        
        # Generate SRT format subtitles with corrected text
        with open(subtitle_filename, "w", encoding="utf-8") as f:
            for i, segment in enumerate(corrected_segments, 1):
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


async def correct_transcription_with_groq(segments: List[Dict[str, Any]], script: str) -> List[Dict[str, Any]]:
    """
    Correct transcription segments by comparing with the original script using Groq API.
    
    Args:
        segments: List of transcription segments from whisper
        script: The original script text
        
    Returns:
        List of corrected transcription segments
    """
    if not settings.GROQ_API_KEY:
        logger.warning("Groq API key not found, using original transcription")
        return segments
    
    try:
        logger.info("Correcting transcription using Groq API")
        corrected_segments = []
        
        # Process in batches to avoid overwhelming the API
        batch_size = 5
        for i in range(0, len(segments), batch_size):
            batch = segments[i:i + batch_size]
            tasks = []
            for segment in batch:
                task = asyncio.create_task(correct_segment(segment, script))
                tasks.append(task)
            
            corrected_batch = await asyncio.gather(*tasks)
            corrected_segments.extend(corrected_batch)
            
        return corrected_segments
        
    except Exception as e:
        logger.error(f"Error correcting transcription: {str(e)}", exc_info=True)
        return segments  # Fallback to original segments


async def correct_segment(segment: Dict[str, Any], script: str) -> Dict[str, Any]:
    """
    Correct a single transcription segment using Groq API.
    
    Args:
        segment: A transcription segment from whisper
        script: The original script text
        
    Returns:
        Corrected transcription segment
    """
    transcribed_text = segment["text"].strip()
    
    # Find the most likely matching part in the script
    script_segment = find_matching_script_segment(transcribed_text, script)
    
    # If we have a very high confidence match, just use that directly
    similarity = get_text_similarity(transcribed_text, script_segment)
    if similarity > 0.9:
        segment["text"] = script_segment
        return segment
    
    try:
        # Use Groq to correct the transcription
        async with httpx.AsyncClient(timeout=30.0) as client:
            headers = {
                "Authorization": f"Bearer {settings.GROQ_API_KEY}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "model": settings.GROQ_MODEL,
                "messages": [
                    {
                        "role": "system", 
                        "content": "You are an AI assistant that corrects transcription errors. Compare the transcribed text with the original script and fix any spelling mistakes, incorrect words, or other errors. Preserve the meaning and style of the original script. Return only the corrected text, nothing else."
                    },
                    {
                        "role": "user",
                        "content": f"Whisper transcription: \"{transcribed_text}\"\n\nOriginal script segment: \"{script_segment}\"\n\nProvide only the corrected text:"
                    }
                ],
                "temperature": 0.1,
                "max_tokens": 200
            }
            
            response = await client.post("https://api.groq.com/openai/v1/chat/completions", json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
            
            corrected_text = data["choices"][0]["message"]["content"].strip()
            # Remove any quotation marks the model might have added
            corrected_text = corrected_text.strip('"\'')
            
            segment["text"] = corrected_text
            return segment
            
    except Exception as e:
        logger.error(f"Error calling Groq API: {str(e)}", exc_info=True)
        # Fallback to the best script segment match
        segment["text"] = script_segment
        return segment


def find_matching_script_segment(transcribed_text: str, script: str) -> str:
    """
    Find the most likely matching segment in the script using similarity.
    
    Args:
        transcribed_text: The transcribed text from whisper
        script: The original script text
        
    Returns:
        The most similar segment from the script
    """
    # Split script into sentences
    sentences = re.split(r'(?<=[.!?]) +', script)
    sentences = [s.strip() for s in sentences if s.strip()]
    
    if not sentences:
        return transcribed_text
    
    # Find the most similar sentence
    best_match = ""
    best_similarity = -1
    
    # Try with individual sentences
    for sentence in sentences:
        similarity = get_text_similarity(transcribed_text.lower(), sentence.lower())
        if similarity > best_similarity:
            best_similarity = similarity
            best_match = sentence
    
    # Try with pairs of consecutive sentences for longer segments
    for i in range(len(sentences) - 1):
        combined = sentences[i] + " " + sentences[i + 1]
        similarity = get_text_similarity(transcribed_text.lower(), combined.lower())
        if similarity > best_similarity:
            best_similarity = similarity
            best_match = combined
    
    return best_match if best_similarity > 0.3 else transcribed_text


def get_text_similarity(text1: str, text2: str) -> float:
    """
    Calculate similarity between two text strings.
    
    Args:
        text1: First text string
        text2: Second text string
        
    Returns:
        Similarity score between 0 and 1
    """
    # Simple word overlap metric
    words1 = set(text1.lower().split())
    words2 = set(text2.lower().split())
    
    if not words1 or not words2:
        return 0.0
    
    intersection = words1.intersection(words2)
    union = words1.union(words2)
    
    return len(intersection) / len(union)


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
