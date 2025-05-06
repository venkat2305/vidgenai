from openai import AsyncOpenAI
from core.config import settings

perplexity_client = AsyncOpenAI(
    api_key=settings.PERPLEXITY_API_KEY,
    base_url="https://api.perplexity.ai"
)
