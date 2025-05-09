import os
import tempfile
import logging
import re
from typing import Dict, Any, List, Protocol
from abc import ABC, abstractmethod
from core.config import settings
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
        """
        Write segments to an SRT file.
        
        Args:
            segments: List of transcription segments
            output_path: Path to save the SRT file
        """
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
        
        Args:
            script: Text script to convert to subtitles
            output_path: Path to save the SRT file
            
        Returns:
            Path to the generated SRT file
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

    async def generate(self, script: str, audio_path: str) -> str:
        temp_dir = tempfile.gettempdir()
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


# import os
# import tempfile
# import logging
# import re
# from abc import ABC, abstractmethod
# from typing import Dict, Any, List, Optional
# from core.config import settings
# from clients.groq_client import groq_client

# logger = logging.getLogger("vidgenai.subtitle_generator")


# class SubtitleSegment:
#     """Represents a single subtitle segment with timing and text."""
#     def __init__(self, index: int, start: float, end: float, text: str):
#         self.index = index
#         self.start = start
#         self.end = end
#         self.text = text.strip()

#     def to_srt_format(self) -> str:
#         """Convert segment to SRT format."""
#         start_time = self.format_timestamp(self.start)
#         end_time = self.format_timestamp(self.end)
#         return f"{self.index}\n{start_time} --> {end_time}\n{self.text}\n\n"

#     @staticmethod
#     def format_timestamp(seconds: float) -> str:
#         """Format seconds into SRT timestamp format (HH:MM:SS,mmm)."""
#         hours = int(seconds // 3600)
#         minutes = int((seconds % 3600) // 60)
#         seconds_float = seconds % 60
#         milliseconds = int((seconds_float - int(seconds_float)) * 1000)

#         return f"{hours:02d}:{minutes:02d}:{int(seconds_float):02d},{milliseconds:03d}"


# class TranscriptionProvider(ABC):
#     """Base class for audio transcription providers."""

#     @abstractmethod
#     async def transcribe(self, audio_path: str) -> List[SubtitleSegment]:
#         """Transcribe audio file and return list of subtitle segments."""
#         pass


# class GroqTranscriptionProvider(TranscriptionProvider):
#     """Transcription using Groq's Whisper API."""

#     def __init__(self, api_key: Optional[str] = None, client=None):
#         self.api_key = api_key or settings.GROQ_API_KEY
#         self.client = client or groq_client
#         if not self.api_key and not self.client:
#             raise ValueError("Either Groq API key or client is required for transcription")

#     async def transcribe(self, audio_path: str) -> List[SubtitleSegment]:
#         logger.info(f"Transcribing audio using Groq Whisper API: {audio_path}")

#         try:
#             # Read audio file as binary data
#             with open(audio_path, "rb") as audio_file:
#                 audio_data = audio_file.read()

#             response = await self.client.audio.transcriptions.create(
#                 file=audio_data,
#                 model="whisper-large-v3-turbo",
#                 response_format="verbose_json"
#             )

#             return self._parse_response(response)
#         except Exception as e:
#             logger.error(f"Error transcribing with Groq: {str(e)}", exc_info=True)
#             raise Exception(f"Failed to transcribe audio with Groq: {str(e)}")

#     def _parse_response(self, result: Dict[str, Any]) -> List[SubtitleSegment]:
#         """Parse the API response into subtitle segments."""
#         segments = []
#         if "segments" not in result:
#             # If segments are not provided, create a basic segment
#             segments.append(SubtitleSegment(
#                 index=1,
#                 start=0.0,
#                 end=float(result.get("duration", 0)),
#                 text=result.get("text", "")
#             ))
#         else:
#             for i, segment in enumerate(result["segments"], 1):
#                 segments.append(SubtitleSegment(
#                     index=i,
#                     start=segment["start"],
#                     end=segment["end"],
#                     text=segment["text"]
#                 ))

#         return segments


# class SimpleTranscriptionProvider(TranscriptionProvider):
#     """Fallback provider that estimates timing based on script text."""

#     def __init__(self, chars_per_second: float = 15.0):
#         self.chars_per_second = chars_per_second

#     async def transcribe(self, audio_path: str, script: str) -> List[SubtitleSegment]:
#         logger.info(f"Generating simple time-based subtitles for: {audio_path}")

#         # Split script into sentences
#         sentences = re.split(r'(?<=[.!?]) +', script)
#         sentences = [s.strip() for s in sentences if s.strip()]

#         # Generate subtitles with estimated timing
#         segments = []
#         current_time = 0

#         for i, sentence in enumerate(sentences, 1):
#             # Estimate duration based on character count
#             duration = max(1.5, len(sentence) / self.chars_per_second)

#             segments.append(SubtitleSegment(
#                 index=i,
#                 start=current_time,
#                 end=current_time + duration,
#                 text=sentence
#             ))

#             current_time += duration

#         return segments


# class TranscriptionProviderFactory:
#     """Factory for creating transcription providers."""

#     @staticmethod
#     def get_provider(provider_type: str) -> TranscriptionProvider:
#         if provider_type.lower() == "groq":
#             return GroqTranscriptionProvider()
#         elif provider_type.lower() == "simple":
#             return SimpleTranscriptionProvider()
#         else:
#             raise ValueError(f"Unsupported transcription provider: {provider_type}")


# class SubtitleGenerator:
#     """Main class for subtitle generation process."""

#     def __init__(self, primary_provider: str = "groq", fallback_provider: Optional[str] = None):
#         self.primary_provider = TranscriptionProviderFactory.get_provider(primary_provider)
#         self.fallback_provider = None
#         if fallback_provider:
#             self.fallback_provider = TranscriptionProviderFactory.get_provider(fallback_provider)
#         self.simple_provider = SimpleTranscriptionProvider()
#         self.temp_dir = tempfile.gettempdir()

#     async def generate_subtitles(self, script: str, audio_path: str) -> str:
#         subtitle_filename = os.path.join(
#             self.temp_dir, f"subtitles_{os.path.basename(audio_path)}.srt"
#         )

#         try:
#             # Try primary provider first
#             logger.info(f"Generating subtitles using primary provider for: {audio_path}")
#             segments = await self.primary_provider.transcribe(audio_path)
#             return self._write_subtitles(segments, subtitle_filename)

#         except Exception as primary_error:
#             logger.error(f"Primary provider failed: {str(primary_error)}", exc_info=True)

#             # Try fallback provider if available
#             if self.fallback_provider:
#                 try:
#                     logger.info(f"Trying fallback provider for: {audio_path}")
#                     segments = await self.fallback_provider.transcribe(audio_path)
#                     return self._write_subtitles(segments, subtitle_filename)
#                 except Exception as fallback_error:
#                     logger.error(f"Fallback provider failed: {str(fallback_error)}", exc_info=True)

#             # Last resort: use simple time-based subtitle generation
#             try:
#                 logger.info("Falling back to simple subtitle generation")
#                 segments = await self.simple_provider.transcribe(audio_path, script)
#                 return self._write_subtitles(segments, subtitle_filename)
#             except Exception as simple_error:
#                 logger.error(f"Simple subtitle generation failed: {str(simple_error)}", exc_info=True)
#                 raise Exception(f"All subtitle generation methods failed: {str(primary_error)}")

#     def _write_subtitles(self, segments: List[SubtitleSegment], output_path: str) -> str:
#         """Write subtitle segments to SRT file."""
#         with open(output_path, "w", encoding="utf-8") as f:
#             for segment in segments:
#                 f.write(segment.to_srt_format())

#         logger.info(f"Generated subtitle file: {output_path}")
#         return output_path

# import os
# import tempfile
# import logging
# import re
# import httpx
# from typing import Dict, Any
# from core.config import settings

# logger = logging.getLogger("vidgenai.subtitle_generator")


# async def generate_subtitles(script: str, audio_path: str) -> str:
#     """
#     Generate subtitles from script and audio.
#     If transcription fails, fall back to simple subtitle generation.
#     """
#     try:
#         temp_dir = tempfile.gettempdir()
#         subtitle_filename = os.path.join(
#             temp_dir, f"subtitles_{os.path.basename(audio_path)}.srt"
#         )

#         # 1. Transcribe audio with Whisper
#         logger.info(f"Transcribing audio with Groq Whisper API: {audio_path}")
#         result = await transcribe_audio_with_groq(audio_path)

#         # 2. Write SRT subtitles directly from transcription segments
#         with open(subtitle_filename, "w", encoding="utf-8") as f:
#             for i, segment in enumerate(result["segments"], 1):
#                 start_time = format_timestamp(segment["start"])
#                 end_time = format_timestamp(segment["end"])
#                 text = segment["text"].strip()
#                 f.write(f"{i}\n")
#                 f.write(f"{start_time} --> {end_time}\n")
#                 f.write(f"{text}\n\n")

#         logger.info(f"Generated subtitle file: {subtitle_filename}")
#         return subtitle_filename

#     except Exception as e:
#         logger.error(f"Error generating subtitles: {str(e)}", exc_info=True)
#         # Fallback to simple time-based subtitle generation
#         try:
#             logger.info("Falling back to simple subtitle generation")
#             return await generate_simple_subtitles(script, subtitle_filename)
#         except Exception as fallback_error:
#             logger.error(
#                 f"Fallback subtitle generation failed: {str(fallback_error)}",
#                 exc_info=True,
#             )
#             raise Exception(f"Failed to generate subtitles: {str(e)}")



# async def transcribe_audio_with_groq(audio_path: str) -> Dict[str, Any]:
#     """
#     Transcribe audio using Groq's Whisper-large-v3-turbo model.
    
#     Args:
#         audio_path: Path to the audio file
        
#     Returns:
#         Dictionary containing transcription results with segments
#     """
#     if not settings.GROQ_API_KEY:
#         raise ValueError("Groq API key is required for transcription")
    
#     logger.info(f"Transcribing audio using Groq Whisper-large-v3-turbo: {audio_path}")
    
#     try:
#         async with httpx.AsyncClient(timeout=120.0) as client:
#             headers = {
#                 "Authorization": f"Bearer {settings.GROQ_API_KEY}",
#             }
            
#             # Read audio file as binary data
#             with open(audio_path, "rb") as audio_file:
#                 audio_data = audio_file.read()
            
#             # Prepare the multipart form data
#             files = {
#                 "file": (os.path.basename(audio_path), audio_data),
#                 "model": (None, "whisper-large-v3-turbo"),
#                 "response_format": (None, "verbose_json"),
#                 "timestamp_granularities[]": (None, "segment"),
#             }
            
#             # Make the API request to Groq's Whisper endpoint
#             response = await client.post(
#                 "https://api.groq.com/openai/v1/audio/transcriptions",
#                 headers=headers,
#                 files=files
#             )
#             response.raise_for_status()
#             result = response.json()
            
#             # Format the result to match the expected structure
#             if "segments" not in result:
#                 # If segments are not provided, create a basic segment
#                 result["segments"] = [{
#                     "start": 0.0,
#                     "end": float(result.get("duration", 0)),
#                     "text": result.get("text", "")
#                 }]
                
#             return result
            
#     except Exception as e:
#         logger.error(f"Error calling Groq Whisper API: {str(e)}", exc_info=True)
#         raise Exception(f"Failed to transcribe audio with Groq: {str(e)}")


# async def generate_simple_subtitles(script: str, output_path: str) -> str:
#     """
#     Generate simple time-based subtitles without audio analysis.
    
#     This is a fallback method if whisper transcription fails.
#     """
#     # Split script into sentences
#     sentences = re.split(r'(?<=[.!?]) +', script)
#     sentences = [s.strip() for s in sentences if s.strip()]
    
#     # Estimate average reading speed (chars per second)
#     chars_per_second = 15
    
#     # Generate subtitles with estimated timing
#     with open(output_path, "w", encoding="utf-8") as f:
#         current_time = 0
        
#         for i, sentence in enumerate(sentences, 1):
#             # Estimate duration based on character count
#             duration = max(1.5, len(sentence) / chars_per_second)
            
#             start_time = format_timestamp(current_time)
#             end_time = format_timestamp(current_time + duration)
            
#             f.write(f"{i}\n")
#             f.write(f"{start_time} --> {end_time}\n")
#             f.write(f"{sentence}\n\n")
            
#             current_time += duration
    
#     logger.info(f"Generated simple subtitle file: {output_path}")
#     return output_path


# def format_timestamp(seconds: float) -> str:
#     """
#     Format seconds into SRT timestamp format (HH:MM:SS,mmm).
#     """
#     hours = int(seconds // 3600)
#     minutes = int((seconds % 3600) // 60)
#     seconds = seconds % 60
#     milliseconds = int((seconds - int(seconds)) * 1000)
    
#     return f"{hours:02d}:{minutes:02d}:{int(seconds):02d},{milliseconds:03d}"
