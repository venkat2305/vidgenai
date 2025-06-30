import modal
import os
from pathlib import Path

# Create Modal app
app = modal.App("vidgenai-backend")

# Define the image with all required dependencies
image = modal.Image.debian_slim(python_version="3.11").pip_install_from_requirements("requirements.txt")

# Environment secrets for Modal
secrets = [
    modal.Secret.from_name("vidgenai-secrets")
]

@app.function(
    image=image,
    secrets=secrets,
    min_containers=1,  # Keep one container warm
    timeout=300,  # 5 minute timeout
)
@modal.asgi_app()
def fastapi_app():
    """
    Modal ASGI app that serves the FastAPI application
    """
    from fastapi import FastAPI, Request, HTTPException, Query
    from fastapi.middleware.cors import CORSMiddleware
    from typing import List, Optional
    import logging
    import os
    
    # Configure logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger("vidgenai")
    
    # Initialize FastAPI app
    web_app = FastAPI(
        title="VidGenAI",
        description="AI-Generated Sports Celebrity History Reels",
        version="1.0.0",
    )

    # Add CORS middleware
    web_app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Database connection variables
    mongodb_client = None
    mongodb_db = None
    
    async def startup_event():
        nonlocal mongodb_client, mongodb_db
        try:
            from motor.motor_asyncio import AsyncIOMotorClient
            mongodb_url = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
            mongodb_db_name = os.getenv("MONGODB_DB_NAME", "vidgenai")
            
            logger.info("Connecting to MongoDB...")
            mongodb_client = AsyncIOMotorClient(mongodb_url)
            mongodb_db = mongodb_client[mongodb_db_name]
            logger.info("Connected to MongoDB successfully")
        except Exception as e:
            logger.error(f"Failed to connect to MongoDB: {e}")
    
    async def shutdown_event():
        nonlocal mongodb_client
        try:
            if mongodb_client:
                mongodb_client.close()
                logger.info("MongoDB connection closed")
        except Exception as e:
            logger.error(f"Error closing MongoDB: {e}")
    
    # Add event handlers
    web_app.add_event_handler("startup", startup_event)
    web_app.add_event_handler("shutdown", shutdown_event)

    # Root endpoint
    @web_app.get("/")
    async def root():
        return {"message": "Welcome to VidGenAI - Sports Celebrity History Reels Generator"}

    # Health check endpoint
    @web_app.get("/health")
    async def health():
        return {"status": "healthy", "mongodb_connected": mongodb_db is not None}

    # Videos endpoints
    @web_app.get("/api/videos/")
    async def get_videos(
        skip: int = Query(0, ge=0),
        limit: int = Query(10, ge=1, le=100),
        status: Optional[str] = None
    ):
        if mongodb_db is None:
            raise HTTPException(status_code=503, detail="Database not available")
        
        try:
            query = {}
            if status:
                query["status"] = status

            videos_collection = mongodb_db.videos
            videos = await videos_collection.find(query).skip(skip).limit(limit).to_list(limit)
            return videos
        except Exception as e:
            logger.error(f"Error fetching videos: {e}")
            raise HTTPException(status_code=500, detail="Failed to fetch videos")

    @web_app.get("/api/videos/{video_id}")
    async def get_video(video_id: str):
        if mongodb_db is None:
            raise HTTPException(status_code=503, detail="Database not available")
        
        try:
            videos_collection = mongodb_db.videos
            video = await videos_collection.find_one({"id": video_id})

            if not video:
                raise HTTPException(status_code=404, detail="Video not found")

            return video
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error fetching video {video_id}: {e}")
            raise HTTPException(status_code=500, detail="Failed to fetch video")

    # Generation endpoint
    @web_app.post("/api/generation/generate")
    async def generate_video(request: dict):
        try:
            # Basic validation
            if not request.get("topic"):
                raise HTTPException(status_code=400, detail="Topic is required")
            
            # For now, return a mock response
            return {
                "message": "Video generation started",
                "video_id": "mock_video_123",
                "status": "processing",
                "topic": request.get("topic")
            }
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error in video generation: {e}")
            raise HTTPException(status_code=500, detail="Failed to start video generation")

    return web_app

# For local deployment
@app.local_entrypoint()
def deploy():
    """Deploy the FastAPI app to Modal"""
    print("🚀 Deploying VidGenAI backend to Modal...")
    print("📡 App will be available at the provided Modal URL") 