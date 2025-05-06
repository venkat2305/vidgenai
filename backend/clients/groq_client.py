from groq import AsyncGroq
from core.config import settings

groq_client = AsyncGroq(
    api_key=settings.GROQ_API_KEY,
)
