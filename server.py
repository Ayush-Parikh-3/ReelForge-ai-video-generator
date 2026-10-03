import os
import json
import asyncio
import logging
import uuid
import time
from queue import Queue, Empty
from threading import Thread
from typing import Optional
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import requests

from config import (
    STATIC_DIR, OUTPUT_DIR, VOICES, DIMENSIONS, SUBTITLE_STYLES,
    BASE_DIR
)
from pipeline import VideoGenerationPipeline

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(title="ReelForge AI Video Studio")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
app.mount("/output", StaticFiles(directory=OUTPUT_DIR), name="output")

class GenerateRequest(BaseModel):
    prompt: str
    scene_count: int = 4
    aspect_ratio: str = "16:9"
    voice_id: str = "en-US-ChristopherNeural"
    subtitle_style: str = "modern"
    include_music: bool = True
    gemini_api_key: Optional[str] = ""
    pixabay_api_key: Optional[str] = ""

class KeyTestRequest(BaseModel):
    gemini_api_key: Optional[str] = ""
    pixabay_api_key: Optional[str] = ""

@app.get("/", response_class=HTMLResponse)
async def serve_index():
    index_file = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_file):
        with open(index_file, "r", encoding="utf-8") as f:
            return HTMLResponse(f.read())
    return HTMLResponse("<h1>Studio is initializing...</h1>")

@app.get("/api/config")
async def get_config():
    """Returns available voice options, aspect ratios, subtitle styles, and server key status."""
    has_gemini = bool(os.getenv("GEMINI_API_KEY", "").strip())
    has_pixabay = bool(os.getenv("PIXABAY_API_KEY", "").strip())
    return {
        "voices": VOICES,
        "aspect_ratios": DIMENSIONS,
        "subtitle_styles": {k: v["label"] for k, v in SUBTITLE_STYLES.items()},
        "has_server_gemini_key": has_gemini,
        "has_server_pixabay_key": has_pixabay
    }

@app.post("/api/test-keys")
async def test_keys(req: KeyTestRequest):
    """
    Tests the validity of keys entered by user or configured in server environment.
    Never saves anything to disk.
    """
    results = {}

    # Test Gemini Key (client key or server env)
    gemini_key = (req.gemini_api_key or os.getenv("GEMINI_API_KEY", "")).strip()
    if gemini_key:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models?key={gemini_key}"
            r = requests.get(url, timeout=6.0)
            if r.status_code == 200:
                is_env = not req.gemini_api_key and bool(os.getenv("GEMINI_API_KEY"))
                msg = "Google Gemini API key verified (from server env)!" if is_env else "Google Gemini API key verified!"
                results["gemini"] = {"valid": True, "message": msg}
            else:
                results["gemini"] = {"valid": False, "message": f"Gemini rejected key (HTTP {r.status_code})."}
        except Exception as e:
            results["gemini"] = {"valid": False, "message": f"Gemini connection error: {e}"}
    else:
        results["gemini"] = {"valid": False, "message": "No Gemini API key provided."}

    # Test Pixabay Key (client key or server env)
    pix_key = (req.pixabay_api_key or os.getenv("PIXABAY_API_KEY", "")).strip()
    if pix_key:
        try:
            url = f"https://pixabay.com/api/videos/?key={pix_key}&q=nature&safesearch=true&per_page=3"
            r = requests.get(url, timeout=6.0)
            if r.status_code == 200:
                is_env = not req.pixabay_api_key and bool(os.getenv("PIXABAY_API_KEY"))
                msg = "Pixabay API key verified (from server env)!" if is_env else "Pixabay API key verified! Stock footages active."
                results["pixabay"] = {"valid": True, "message": msg}
            else:
                results["pixabay"] = {"valid": False, "message": f"Pixabay rejected key (HTTP {r.status_code})."}
        except Exception as e:
            results["pixabay"] = {"valid": False, "message": f"Pixabay connection error: {e}"}
    else:
        results["pixabay"] = {"valid": False, "message": "No Pixabay API key provided."}

    return results

@app.post("/api/generate")
async def generate_video_sync(req: GenerateRequest):
    """Synchronous generation endpoint using browser keys or server env fallback."""
    if not req.prompt.strip():
        raise HTTPException(status_code=400, detail="Prompt text cannot be empty.")

    pipeline = VideoGenerationPipeline()
    try:
        result = pipeline.run(
            prompt=req.prompt,
            scene_count=req.scene_count,
            aspect_ratio=req.aspect_ratio,
            voice_id=req.voice_id,
            subtitle_style=req.subtitle_style,
            include_music=req.include_music,
            gemini_api_key=(req.gemini_api_key or os.getenv("GEMINI_API_KEY", "")).strip(),
            pixabay_api_key=(req.pixabay_api_key or os.getenv("PIXABAY_API_KEY", "")).strip()
        )
        return result
    except Exception as e:
        logger.error(f"Generation error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

# In-memory job state tracker for resilient mobile generation
JOBS = {}
MAX_JOBS_STORED = 200
JOB_TTL_SECONDS = 3600  # 1 hour

def cleanup_old_jobs():
    """Remove expired jobs to prevent memory growth."""
    now = time.time()
    for jid in list(JOBS.keys()):
        if now - JOBS[jid].get("created_at", now) > JOB_TTL_SECONDS:
            JOBS.pop(jid, None)
    if len(JOBS) > MAX_JOBS_STORED:
        sorted_jobs = sorted(JOBS.items(), key=lambda item: item[1].get("created_at", 0))
        for jid, _ in sorted_jobs[: len(JOBS) - MAX_JOBS_STORED]:
            JOBS.pop(jid, None)

@app.post("/api/start-generation")
async def start_generation(req: GenerateRequest):
    """
    Starts an asynchronous video generation job.
    Returns a unique job_id immediately. Clients (especially mobile phones)
    poll /api/job-status/{job_id}, completely eliminating SSE timeout
    and cellular connection drop issues.
    """
    if not req.prompt.strip():
        raise HTTPException(status_code=400, detail="Prompt text cannot be empty.")

    cleanup_old_jobs()

    job_id = str(uuid.uuid4())
    effective_gemini_key = (req.gemini_api_key or os.getenv("GEMINI_API_KEY", "")).strip()
    effective_pixabay_key = (req.pixabay_api_key or os.getenv("PIXABAY_API_KEY", "")).strip()

    JOBS[job_id] = {
        "status": "running",
        "stage": "starting",
        "percent": 5,
        "message": "Initializing ReelForge engine...",
        "result": None,
        "error": None,
        "created_at": time.time()
    }

    def progress_callback(event_data):
        if job_id in JOBS:
            if "stage" in event_data:
                JOBS[job_id]["stage"] = event_data["stage"]
            if "percent" in event_data:
                JOBS[job_id]["percent"] = event_data["percent"]
            if "message" in event_data:
                JOBS[job_id]["message"] = event_data["message"]

    def worker():
        try:
            pipeline = VideoGenerationPipeline()
            result = pipeline.run(
                prompt=req.prompt,
                scene_count=req.scene_count,
                aspect_ratio=req.aspect_ratio,
                voice_id=req.voice_id,
                subtitle_style=req.subtitle_style,
                include_music=req.include_music,
                gemini_api_key=effective_gemini_key,
                pixabay_api_key=effective_pixabay_key,
                progress_callback=progress_callback
            )
            if job_id in JOBS:
                JOBS[job_id]["status"] = "done"
                JOBS[job_id]["stage"] = "done"
                JOBS[job_id]["percent"] = 100
                JOBS[job_id]["message"] = "Video created successfully!"
                JOBS[job_id]["result"] = result
        except Exception as e:
            logger.error(f"Pipeline worker failure for job {job_id}: {e}", exc_info=True)
            if job_id in JOBS:
                JOBS[job_id]["status"] = "error"
                JOBS[job_id]["stage"] = "error"
                JOBS[job_id]["percent"] = 0
                JOBS[job_id]["error"] = str(e)

    Thread(target=worker, daemon=True).start()

    return {"job_id": job_id}

@app.get("/api/job-status/{job_id}")
async def get_job_status(job_id: str):
    """
    Returns current status and progress of a video generation job.
    """
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found or expired.")
    return {
        "job_id": job_id,
        "status": job["status"],
        "stage": job["stage"],
        "percent": job["percent"],
        "message": job["message"],
        "result": job["result"],
        "error": job["error"]
    }

@app.get("/api/generate-stream")
async def generate_video_stream(
    prompt: str,
    scene_count: int = 4,
    aspect_ratio: str = "16:9",
    voice_id: str = "en-US-ChristopherNeural",
    subtitle_style: str = "modern",
    include_music: bool = True,
    gemini_api_key: str = "",
    pixabay_api_key: str = ""
):
    """
    Server-Sent Events (SSE) streaming endpoint.
    Uses browser-provided keys directly, or server env keys if set.
    """
    event_queue = Queue()

    effective_gemini_key = (gemini_api_key or os.getenv("GEMINI_API_KEY", "")).strip()
    effective_pixabay_key = (pixabay_api_key or os.getenv("PIXABAY_API_KEY", "")).strip()

    def progress_callback(event_data):
        event_queue.put(event_data)

    def worker():
        try:
            pipeline = VideoGenerationPipeline()
            result = pipeline.run(
                prompt=prompt,
                scene_count=scene_count,
                aspect_ratio=aspect_ratio,
                voice_id=voice_id,
                subtitle_style=subtitle_style,
                include_music=include_music,
                gemini_api_key=effective_gemini_key,
                pixabay_api_key=effective_pixabay_key,
                progress_callback=progress_callback
            )
            event_queue.put({"stage": "done", "percent": 100, "result": result})
        except Exception as e:
            logger.error(f"Pipeline worker failure: {e}", exc_info=True)
            event_queue.put({"stage": "error", "percent": 0, "error": str(e)})

    Thread(target=worker, daemon=True).start()

    async def event_generator():
        while True:
            try:
                event = await asyncio.to_thread(event_queue.get, True, 0.25)
                yield f"data: {json.dumps(event)}\n\n"
                if event.get("stage") in ("done", "error"):
                    break
            except Empty:
                yield ": keepalive\n\n"
                await asyncio.sleep(0.5)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("server:app", host="0.0.0.0", port=port, reload=True)
