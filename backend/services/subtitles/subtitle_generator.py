import os
import tempfile
import logging
import re
from typing import Dict, Any, List, Protocol
from abc import ABC, abstractmethod
from clients.groq_client import groq_client

logger = logging.getLogger("vidgenai.subtitle_generator")


class TranscriptionSegment(Protocol):
    """Protocol defining the structure of a transcription segment."""
    start: float
    end: float
    text: str


class TranscriptionProvider(ABC):
    @abstractmethod
    async def transcribe(self, audio_path: str) -> List[Dict[str, Any]]:
        """
        Transcribe audio file and return segments.
        Args:
            audio_path: Path to the audio file
        Returns:
            List of segments with start time, end time, and text
        """
        pass


class GroqTranscriptionProvider(TranscriptionProvider):
    def __init__(self):
        self.client = groq_client

    async def transcribe(self, audio_path: str) -> List[Dict[str, Any]]:
        logger.info(f"Transcribing audio using Groq Whisper-large-v3-turbo: {audio_path}")

        try:
            with open(audio_path, "rb") as audio_file:
                response = await self.client.audio.transcriptions.create(
                    file=(os.path.basename(audio_path), audio_file.read()),
                    model="whisper-large-v3-turbo",
                    response_format="verbose_json",
                    timestamp_granularities=["segment"]
                )

                result = response.dict()
                if "segments" not in result or not result["segments"]:
                    return [{
                        "start": 0.0,
                        "end": float(result.get("duration", 0)),
                        "text": result.get("text", "")
                    }]
                return result["segments"]

        except Exception as e:
            logger.error(f"Error calling Groq Whisper API: {str(e)}", exc_info=True)
            raise Exception(f"Failed to transcribe audio with Groq: {str(e)}")


class SubtitleFormatter:
    """Class responsible for formatting subtitles in SRT format."""

    @staticmethod
    def format_timestamp(seconds: float) -> str:
        """
        Format seconds into SRT timestamp format (HH:MM:SS,mmm).
        """
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        seconds_int = int(seconds)
        milliseconds = int((seconds - seconds_int) * 1000)

        return f"{hours:02d}:{minutes:02d}:{seconds_int:02d},{milliseconds:03d}"

    @staticmethod
    def write_srt_file(segments: List[Dict[str, Any]], output_path: str) -> None:
        with open(output_path, "w", encoding="utf-8") as f:
            for i, segment in enumerate(segments, 1):
                start_time = SubtitleFormatter.format_timestamp(segment["start"])
                end_time = SubtitleFormatter.format_timestamp(segment["end"])
                text = segment["text"].strip()
                f.write(f"{i}\n")
                f.write(f"{start_time} --> {end_time}\n")
                f.write(f"{text}\n\n")


class SimpleSubtitleGenerator:
    """Fallback subtitle generator using simple timing estimation."""

    @staticmethod
    async def generate(script: str, output_path: str) -> str:
        """
        Generate simple time-based subtitles without audio analysis.
        """
        sentences = re.split(r"(?<=[.!?]) +", script)
        sentences = [s.strip() for s in sentences if s.strip()]
        chars_per_second = 15

        segments = []
        current_time = 0.0

        for sentence in sentences:
            duration = max(1.5, len(sentence) / chars_per_second)
            segments.append({
                "start": current_time,
                "end": current_time + duration,
                "text": sentence
            })
            current_time += duration

        SubtitleFormatter.write_srt_file(segments, output_path)
        logger.info(f"Generated simple subtitle file: {output_path}")
        return output_path


class SubtitleGenerator:
    def __init__(self):
        self.providers = [
            GroqTranscriptionProvider()
        ]

    async def generate(self, script: str, audio_path: str, temp_dir: str | None = None) -> str:
        temp_dir = temp_dir or tempfile.gettempdir()
        subtitle_filename = os.path.join(
            temp_dir, f"subtitles_{os.path.basename(audio_path)}.srt"
        )

        for provider in self.providers:
            try:
                logger.info(f"Attempting transcription with {provider.__class__.__name__}")
                segments = await provider.transcribe(audio_path)
                SubtitleFormatter.write_srt_file(segments, subtitle_filename)
                logger.info(f"Generated subtitle file: {subtitle_filename}")
                return subtitle_filename
            except Exception as e:
                logger.error(
                    f"Transcription failed with {provider.__class__.__name__}: {str(e)}",
                    exc_info=True
                )

        logger.info("All transcription providers failed, falling back to simple generation")
        return await SimpleSubtitleGenerator.generate(script, subtitle_filename)
