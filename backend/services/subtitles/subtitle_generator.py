import os
import tempfile
import logging
import re
from typing import Dict, Any, List, Protocol, Tuple, Optional
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from clients.groq_client import groq_client

logger = logging.getLogger("vidgenai.subtitle_generator")


@dataclass
class SubtitleSegment:
    """A detailed structure for subtitle segments with support for word-level timing."""
    start: float
    end: float
    text: str
    word_timings: List[Tuple[float, float, str]] = field(default_factory=list)
    # For ASS styling
    style: str = "Default"
    highlighted_indices: List[int] = field(default_factory=list)  # Indices of characters to highlight


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


class SubtitleFormatter(ABC):
    """Abstract base class for subtitle formatters."""
    @abstractmethod
    def format(self, segments: List[SubtitleSegment], output_path: str) -> str:
        pass


class SRTFormatter(SubtitleFormatter):
    """Formatter for SRT subtitle format (no styling support)."""
    @staticmethod
    def format_timestamp(seconds: float) -> str:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        seconds_int = int(seconds)
        milliseconds = int((seconds - seconds_int) * 1000)
        return f"{hours:02d}:{minutes:02d}:{seconds_int:02d},{milliseconds:03d}"

    def format(self, segments: List[SubtitleSegment], output_path: str) -> str:
        with open(output_path, "w", encoding="utf-8") as f:
            for i, segment in enumerate(segments, 1):
                start_time = self.format_timestamp(segment.start)
                end_time = self.format_timestamp(segment.end)
                text = segment.text.strip()
                f.write(f"{i}\n")
                f.write(f"{start_time} --> {end_time}\n")
                f.write(f"{text}\n\n")
        return output_path


class ASSFormatter(SubtitleFormatter):
    """Formatter for ASS subtitle format (supports styling and word highlighting)."""
    def __init__(self, styles: Dict[str, Dict[str, Any]] = None):
        self.styles = styles or {
            "Default": {
                "Fontname": "Arial",
                "Fontsize": "24",
                "PrimaryColour": "&H00FFFFFF",  # White
                "Alignment": "8"  # Bottom center
            },
            "Highlight": {
                "Fontname": "Arial",
                "Fontsize": "24",
                "PrimaryColour": "&H0000FFFF",  # Yellow
                "Alignment": "8"
            }
        }

    def format_timestamp(self, seconds: float) -> str:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        seconds_int = int(seconds % 60)
        centiseconds = int((seconds - int(seconds)) * 100)
        return f"{hours}:{minutes:02d}:{seconds_int:02d}.{centiseconds:02d}"

    def format(self, segments: List[SubtitleSegment], output_path: str) -> str:
        header = (
            "[Script Info]\n"
            "Title: Generated Subtitles\n"
            "ScriptType: v4.00+\n"
            "PlayResX: 1280\n"
            "PlayResY: 720\n\n"
            "[V4+ Styles]\n"
            "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
        )
        styles_section = []
        for name, props in self.styles.items():
            styles_section.append(
                f"Style: {name},{props['Fontname']},{props['Fontsize']},{props['PrimaryColour']},&H000000FF,&H00000000,&H64000000,0,0,0,0,100,100,0,0,1,2,2,{props['Alignment']},10,10,10,1"
            )
        events_section = [
            "\n[Events]\n"
            "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
        ]
        for seg in segments:
            text = seg.text
            if seg.highlighted_indices:
                # Apply inline formatting for highlighted characters
                formatted_text = []
                for i, char in enumerate(text):
                    if i in seg.highlighted_indices:
                        formatted_text.append(f"{{\\c&H0000FFFF&}}{char}{{\\c&HFFFFFF&}}")
                    else:
                        formatted_text.append(char)
                text = "".join(formatted_text)
            start = self.format_timestamp(seg.start)
            end = self.format_timestamp(seg.end)
            events_section.append(
                f"Dialogue: 0,{start},{end},{seg.style},,0,0,0,,{text}"
            )
        content = header + "\n".join(styles_section) + "\n".join(events_section)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(content)
        return output_path


class SimpleSubtitleGenerator:
    """Fallback subtitle generator using simple timing estimation."""
    @staticmethod
    async def generate(script: str, output_path: str, formatter: SubtitleFormatter = SRTFormatter()) -> str:
        sentences = re.split(r"(?<=[.!?]) +", script)
        sentences = [s.strip() for s in sentences if s.strip()]
        chars_per_second = 15
        segments = []
        current_time = 0.0
        for sentence in sentences:
            duration = max(1.5, len(sentence) / chars_per_second)
            segments.append(SubtitleSegment(
                start=current_time,
                end=current_time + duration,
                text=sentence
            ))
            current_time += duration
        logger.info(f"Generated simple subtitle file: {output_path}")
        return formatter.format(segments, output_path)


class ElevenLabsAlignmentProcessor:
    """Processor for Eleven Labs alignment data to create subtitle segments."""
    @staticmethod
    def process_alignment(alignment_data: Dict[str, Any], granularity: str = "word") -> List[SubtitleSegment]:
        if not alignment_data or "normalized_alignment" not in alignment_data:
            logger.warning("No alignment data provided from Eleven Labs.")
            return []

        # Extract alignment data safely, handling both dict and pydantic models
        alignment = alignment_data.get("normalized_alignment") if isinstance(alignment_data, dict) else alignment_data.normalized_alignment
        
        # Handle either dict or pydantic model for the alignment data
        if isinstance(alignment, dict):
            chars = alignment.get("characters", [])
            starts = alignment.get("character_start_times_seconds", [])
            ends = alignment.get("character_end_times_seconds", [])
        else:
            chars = alignment.characters
            starts = alignment.character_start_times_seconds
            ends = alignment.character_end_times_seconds

        if granularity == "word":
            # Group characters into words
            words = []
            current_word = []
            for char, start, end in zip(chars, starts, ends):
                if char == " ":
                    if current_word:
                        words.append(current_word)
                        current_word = []
                else:
                    current_word.append((char, start, end))
            if current_word:
                words.append(current_word)

            segments = []
            for word_chars in words:
                word_text = "".join([c[0] for c in word_chars])
                word_start = word_chars[0][1]
                word_end = word_chars[-1][2]
                # Optionally, highlight the first character of each word
                highlighted = [0] if len(word_text) > 0 else []
                segments.append(SubtitleSegment(
                    start=word_start,
                    end=word_end,
                    text=word_text,
                    word_timings=[(c[1], c[2], c[0]) for c in word_chars],
                    highlighted_indices=highlighted
                ))
        else:  # character-level granularity
            segments = []
            for char, start, end in zip(chars, starts, ends):
                if char != " ":
                    segments.append(SubtitleSegment(
                        start=start,
                        end=end,
                        text=char,
                        highlighted_indices=[0]  # Highlight each character
                    ))

        logger.info(f"Processed Eleven Labs alignment into {len(segments)} segments at {granularity} level.")
        return segments


class SubtitleGenerator:
    def __init__(self):
        self.providers = [GroqTranscriptionProvider()]
        self.formatters = {
            "srt": SRTFormatter(),
            "ass": ASSFormatter()
        }

    async def generate(self, script: str, audio_path: str, timestamp_data: Dict[str, Any] = None, format_type: str = "srt", temp_dir: Optional[str]= None) -> str:
        temp_dir = temp_dir or tempfile.gettempdir()
        subtitle_filename = os.path.join(
            temp_dir, f"subtitles_{os.path.basename(audio_path)}_{format_type}.{format_type}"
        )
        formatter = self.formatters.get(format_type, self.formatters["srt"])

        # Step 1: Check if Eleven Labs timestamp data is available
        if timestamp_data and "normalized_alignment" in timestamp_data:
            logger.info("Using Eleven Labs alignment data for subtitle generation.")
            segments = ElevenLabsAlignmentProcessor.process_alignment(timestamp_data, granularity="word")
            if segments:
                return formatter.format(segments, subtitle_filename)

        # Step 2: Fall back to transcription providers
        for provider in self.providers:
            try:
                logger.info(f"Attempting transcription with {provider.__class__.__name__}")
                raw_segments = await provider.transcribe(audio_path)
                segments = [
                    SubtitleSegment(start=seg["start"], end=seg["end"], text=seg["text"])
                    for seg in raw_segments
                ]
                logger.info(f"Generated subtitle file: {subtitle_filename}")
                return formatter.format(segments, subtitle_filename)
            except Exception as e:
                logger.error(
                    f"Transcription failed with {provider.__class__.__name__}: {str(e)}",
                    exc_info=True
                )

        # Step 3: Fall back to simple generation if all else fails
        logger.info("All transcription providers failed, falling back to simple generation")
        return await SimpleSubtitleGenerator.generate(script, subtitle_filename, formatter)
