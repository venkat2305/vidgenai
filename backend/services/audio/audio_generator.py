import os
import tempfile
import logging
import base64
from clients.groq_client import groq_client
from clients.eleven_labs import generate_audio_with_eleven_labs
from core.constants import EL_MATILDA_VOICE_ID


class AudioGenerator:
    def __init__(self):
        self.logger = logging.getLogger("vidgenai.audio_generator")
        self.temp_dir = tempfile.gettempdir()

    async def _generate_with_eleven_labs(self, script: str, audio_filename: str) -> str:
        try:
            response = await generate_audio_with_eleven_labs(
                text=script,
                voice_id=EL_MATILDA_VOICE_ID
            )

            audio_data = base64.b64decode(response.audio_base_64)
            with open(audio_filename, "wb") as f:
                f.write(audio_data)

            self.logger.info(f"Generated audio file with ElevenLabs: {audio_filename}")
            return audio_filename
        except Exception as e:
            self.logger.error(f"Error generating audio with ElevenLabs: {str(e)}")
            raise Exception(f"Failed to generate audio with ElevenLabs: {str(e)}")

    async def _generate_with_groq(self, script: str, audio_filename: str) -> str:
        try:
            response = await groq_client.audio.speech.create(
                model="playai-tts",
                input=script,
                voice="Chip-PlayAI",
                response_format="wav"
            )

            audio_data = await response.read()
            with open(audio_filename, "wb") as f:
                f.write(audio_data)
            self.logger.info(f"Generated audio file: {audio_filename}")
            return audio_filename
        except Exception as e:
            self.logger.error(f"Error generating audio with Groq: {str(e)}")
            raise Exception(f"Failed to generate audio: {str(e)}")

    async def _generate_with_edge_tts(self, script: str, audio_filename: str) -> str:
        import edge_tts
        voice = "en-US-GuyNeural"
        communicate = edge_tts.Communicate(script, voice)
        await communicate.save(audio_filename)
        self.logger.info(f"Generated audio file with edge-tts: {audio_filename}")
        return audio_filename

    async def generate_audio(self, script: str) -> str:
        audio_filename = os.path.join(self.temp_dir, f"audio_{hash(script)}.wav")
        providers = [
            ("ElevenLabs", self._generate_with_eleven_labs),
            ("Groq", self._generate_with_groq),
            ("EdgeTTS", self._generate_with_edge_tts),
        ]
        errors = []

        for name, provider in providers:
            try:
                self.logger.info(f"Trying {name} for audio generation")
                return await provider(script, audio_filename)
            except Exception as e:
                self.logger.error(f"{name} generation failed: {str(e)}", exc_info=True)
                errors.append(f"{name}: {str(e)}")

        # If all providers fail, raise a single exception with all error messages
        error_message = "All audio generation providers failed:\n" + "\n".join(errors)
        raise Exception(error_message)
