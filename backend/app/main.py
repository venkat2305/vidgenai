from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
import logging

from app.api.routes import video, generation
from app.db.mongodb import connect_to_mongo, close_mongo_connection
from app.utils.error_handlers import handle_exception

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("vidgenai")

# Initialize FastAPI app
app = FastAPI(
    title="VidGenAI",
    description="AI-Generated Sports Celebrity History Reels",
    version="1.0.0",
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return await handle_exception(request, exc)

# Database connection events
app.add_event_handler("startup", connect_to_mongo)
app.add_event_handler("shutdown", close_mongo_connection)

# Include routers
# app.include_router(video.router, prefix="/api/videos", tags=["videos"])
app.include_router(generation.router, prefix="/api/generation", tags=["generation"])

# Root endpoint
@app.get("/")
async def root():
    return {"message": "Welcome to VidGenAI - Sports Celebrity History Reels Generator"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
