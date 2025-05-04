from motor.motor_asyncio import AsyncIOMotorClient
import logging
from core.config import settings

logger = logging.getLogger("vidgenai.db")


class MongoDB:
    client: AsyncIOMotorClient = None
    db = None


mongodb = MongoDB()


async def connect_to_mongo():
    """Connect to MongoDB on startup."""
    logger.info("Connecting to MongoDB...")
    mongodb.client = AsyncIOMotorClient(settings.MONGODB_URL)
    mongodb.db = mongodb.client[settings.MONGODB_DB_NAME]
    logger.info("Connected to MongoDB")


async def close_mongo_connection():
    """Close MongoDB connection on shutdown."""
    logger.info("Closing MongoDB connection...")
    if mongodb.client:
        mongodb.client.close()
    logger.info("MongoDB connection closed")
