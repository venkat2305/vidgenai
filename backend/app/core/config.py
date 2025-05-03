import os
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # MongoDB settings
    MONGODB_URL: str = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
    MONGODB_DB_NAME: str = os.getenv("MONGODB_DB_NAME", "vidgenai")

    # Cloudflare R2 settings
    R2_ACCESS_KEY_ID: str = os.getenv("R2_ACCESS_KEY_ID")
    R2_SECRET_ACCESS_KEY: str = os.getenv("R2_SECRET_ACCESS_KEY")
    R2_BUCKET_NAME: str = os.getenv("R2_BUCKET_NAME", "vidgenai-videos")
    R2_ACCOUNT_ID: str = os.getenv("R2_ACCOUNT_ID")
    R2_ENDPOINT_URL: str = os.getenv("R2_ENDPOINT_URL", f"https://{os.getenv('R2_ACCOUNT_ID')}.r2.cloudflarestorage.com")
    R2_PUBLIC_URL_BASE: str = os.getenv("R2_PUBLIC_URL_BASE", f"https://{os.getenv('R2_BUCKET_NAME')}.{os.getenv('R2_ACCOUNT_ID')}.r2.cloudflarestorage.com")

    # API keys
    GROQ_API_KEY: Optional[str] = os.getenv("GROQ_API_KEY")
    SERP_API_KEY: Optional[str] = os.getenv("SERP_API_KEY")

    # Video generation settings
    DEFAULT_VIDEO_QUALITY: str = os.getenv("DEFAULT_VIDEO_QUALITY", "720p")
    MAX_VIDEO_DURATION: int = int(os.getenv("MAX_VIDEO_DURATION", "60"))  # seconds

    # Model settings
    GROQ_MODEL: str = os.getenv("GROQ_MODEL", "llama3-70b-8192")

    class Config:
        env_file = ".env"


settings = Settings()
