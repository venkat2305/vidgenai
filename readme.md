# VidGenAI

VidGenAI generates short form video "reels" that highlight the career of a sports celebrity.  It is composed of a **FastAPI** backend that orchestrates all of the media generation and a **Next.js** frontend used to browse and create new reels.

## Features

- AI generated script using Gemini, Groq or Perplexity models
- Automatic image search via Brave/Serp API
- Text‑to‑speech audio generation (ElevenLabs, Groq or Edge TTS)
- Subtitle generation using Groq Whisper
- Video composition with dynamic zoom/pan effects and subtitles via FFmpeg/OpenCV
- Assets uploaded to Cloudflare R2 and metadata stored in MongoDB

## Repository Structure

```
backend/   FastAPI service and media processing code
frontend/  Next.js 15 application
```

## Running Locally

1. Create a `.env` file with the required settings (see **Environment Variables** below).
2. Install Python dependencies and start the API:

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload
```

3. Install frontend dependencies and start the UI:

```bash
cd ../frontend
npm install
npm run dev
```

Alternatively you can start the backend with Docker:

```bash
docker-compose up --build
```

## Environment Variables

The backend requires several API keys and storage settings.  Below are the most important variables used in `backend/core/config.py`:

- `MONGODB_URL` – connection string for MongoDB
- `MONGODB_DB_NAME` – database name
- `GROQ_API_KEY`, `GEMINI_API_KEY`, `PERPLEXITY_API_KEY` – LLM provider keys
- `SERP_API_KEY` or `BRAVE_API_KEY` – image search providers
- `ELEVENLABS_API_KEY` – text to speech provider
- `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET_NAME`, `R2_ACCOUNT_ID`, `R2_ENDPOINT_URL`, `R2_PUBLIC_URL_BASE` – Cloudflare R2 storage configuration

## API Overview

- `POST /api/generation/` – start reel generation
- `GET /api/generation/{id}` – retrieve status and metadata of a generation job
- `GET /api/videos/` – list generated reels
- `GET /api/videos/{id}` – get a specific reel

## Frontend

The Next.js app provides pages to explore existing reels, view progress of a generation job and create new ones.  See `frontend/README.md` for generic Next.js commands.

## License

This project is provided as-is for demonstration purposes.
