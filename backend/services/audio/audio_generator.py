import os
import tempfile
import logging
import aiohttp
from core.config import settings

logger = logging.getLogger("vidgenai.audio_generator")


async def generate_audio(script: str) -> str:
    try:
        # Create a temporary file for the audio
        temp_dir = tempfile.gettempdir()
        audio_filename = os.path.join(temp_dir, f"audio_{hash(script)}.wav")

        # Use Groq API for text-to-speech
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
                json=payload
            ) as response:
                if response.status == 200:
                    # Save the audio content to a file
                    with open(audio_filename, "wb") as f:
                        f.write(await response.read())

                    logger.info(f"Generated audio file: {audio_filename}")
                    return audio_filename
                else:
                    error_text = await response.text()
                    logger.error(f"Error generating audio: {response.status} - {error_text}")
                    raise Exception(f"Failed to generate audio: {error_text}")

    except Exception as e:
        logger.error(f"Error in audio generation: {str(e)}", exc_info=True)

        # Fallback to edge-tts if Groq fails
        try:
            logger.info("Falling back to edge-tts for audio generation")
            import edge_tts

            communicate = edge_tts.Communicate(script, "en-US-GuyNeural")
            await communicate.save(audio_filename)

            logger.info(f"Generated audio file with edge-tts: {audio_filename}")
            return audio_filename

        except Exception as fallback_error:
            logger.error(f"Fallback audio generation failed: {str(fallback_error)}", exc_info=True)
            raise Exception(f"Failed to generate audio: {str(e)}")
