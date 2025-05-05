import os
import tempfile
import logging
import aiohttp
from core.config import settings


class AudioGenerator:
    def __init__(self):
        self.logger = logging.getLogger("vidgenai.audio_generator")
        self.temp_dir = tempfile.gettempdir()

    async def _generate_with_groq(self, script: str, audio_filename: str) -> str:
        async with aiohttp.ClientSession() as session:
            headers = {
                "Authorization": f"Bearer {settings.GROQ_API_KEY}",
                "Content-Type": "application/json"
            }
            payload = {
                "model": "playai-tts",
                "input": script,
                "voice": "Arista-PlayAI",
                "response_format": "wav"
            }
            async with session.post(
                "https://api.groq.com/openai/v1/audio/speech",
                headers=headers,
                json=payload,
            ) as response:
                if response.status == 200:
                    with open(audio_filename, "wb") as f:
                        f.write(await response.read())
                    self.logger.info(f"Generated audio file: {audio_filename}")
                    return audio_filename
                else:
                    error_text = await response.text()
                    self.logger.error(
                        f"Error generating audio: {response.status} - {error_text}"
                    )
                    raise Exception(f"Failed to generate audio: {error_text}")

    async def _generate_with_edge_tts(self, script: str, audio_filename: str) -> str:
        import edge_tts

        voice = "en-US-GuyNeural"
        communicate = edge_tts.Communicate(script, voice)
        await communicate.save(audio_filename)
        self.logger.info(f"Generated audio file with edge-tts: {audio_filename}")
        return audio_filename

    async def generate_audio(self, script: str) -> str:
        audio_filename = os.path.join(self.temp_dir, f"audio_{hash(script)}.wav")
        try:
            return await self._generate_with_edge_tts(script, audio_filename)
        except Exception as e:
            self.logger.error(f"Error in audio generation: {str(e)}", exc_info=True)
            self.logger.info("Falling back to edge-tts for audio generation")
            return await self._generate_with_edge_tts(script, audio_filename)
