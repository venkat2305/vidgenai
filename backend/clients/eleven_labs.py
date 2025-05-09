from elevenlabs import ElevenLabs
from core.config import settings

client = ElevenLabs(
    api_key=settings.ELEVENLABS_API_KEY,
)


async def generate_audio_with_eleven_labs(text: str, voice_id: str = "XrExE9yKIg1WjnnlVkGX"):
    try:
        audio_res = client.text_to_speech.convert_with_timestamps(
            voice_id=voice_id,
            text=text,
            model_id="eleven_turbo_v2_5"
        )
        return audio_res
    except Exception as e:
        raise Exception(f"ElevenLabs audio generation failed: {str(e)}")
