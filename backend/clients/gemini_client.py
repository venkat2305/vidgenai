from google import genai
from core.config import settings

gemini_client = genai.Client(api_key=settings.GEMINI_API_KEY)