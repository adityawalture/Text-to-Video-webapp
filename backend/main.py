import os
import time
import hashlib
from typing import Optional, Dict, Tuple

import requests
from fastapi import FastAPI, Form, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

load_dotenv()

# Config 
VADOO_GENERATE_URL = "https://viralapi.vadoo.tv/api/generate_video"
VADOO_API_KEY = os.getenv("VADOO_API_KEY", "")
BACKEND_BASE_URL = os.getenv("BACKEND_BASE_URL", "").rstrip("/")
REQUEST_TIMEOUT = 60
USE_MOCK_ON_FAIL = True
MOCK_VIDEO_URL = False

# Vadoo durations start at 30–60s; UI loops first N seconds for demo
VADOO_DEFAULT_DURATION = "30-60"

if not BACKEND_BASE_URL and not USE_MOCK_ON_FAIL:
    raise RuntimeError("BACKEND_BASE_URL must be set for webhooks or enable USE_MOCK_ON_FAIL.")

# App
app = FastAPI(title="AI Video Generator (Vadoo AI, Webhook)", version="2.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory stores
# TTL cache for final URLs (prompt/style -> url)
class TTLCache:
    def __init__(self, ttl_seconds: int = 3600, max_items: int = 256):
        self.ttl = ttl_seconds
        self.max = max_items
        self._store: Dict[str, Tuple[str, float]] = {}
    def _evict_if_needed(self): 
        if len(self._store) > self.max:
            oldest = min(self._store, key=lambda k: self._store[k][1])
            self._store.pop(oldest, None)
    def get(self, key: str) -> Optional[str]:
        v = self._store.get(key)
        if not v: return None
        url, ts = v
        if time.time() - ts > self.ttl:
            self._store.pop(key, None)
            return None
        return url
    def set(self, key: str, value: str):
        self._store[key] = (value, time.time())
        self._evict_if_needed()

cache = TTLCache(ttl_seconds=3600, max_items=256)

# Job store: job_id -> {"status": "queued"|"processing"|"complete"|"error", "url": Optional[str], "note": Optional[str]}
JOBS: Dict[str, Dict[str, Optional[str]]] = {}

# Prompt templates
STYLE_TEMPLATES = {
    "cinematic": "Style: cinematic, high quality, dramatic lighting, shallow depth of field, smooth camera motion.",
    "anime":     "Style: anime, vibrant colors, dynamic motion lines, stylized character design.",
    "realism":   "Style: photorealistic, high detail, natural lighting, subtle camera shake.",
}
DEFAULT_STYLE = "cinematic"

STYLE_TO_VADOO = {
    
    "cinematic": {"theme": "Hormozi_1", "style": "cinematic", "voice": "Charlie", "aspect_ratio": "9:16"},
    "anime":     {"theme": "Hormozi_1", "style": "anime",      "voice": "Charlie", "aspect_ratio": "9:16"},
    "realism":   {"theme": "Hormozi_1", "style": "photographic","voice": "Charlie", "aspect_ratio": "9:16"},
}

def build_prompt(user_prompt: str, style_key: str = DEFAULT_STYLE) -> str:
    suffix = STYLE_TEMPLATES.get(style_key, STYLE_TEMPLATES[DEFAULT_STYLE])
    return f"{user_prompt.strip()}. {suffix}"

def cache_key_for(prompt: str, style: str, duration_client_sec: int) -> str:
    return hashlib.sha256(f"{prompt}||{style}||{duration_client_sec}".encode("utf-8")).hexdigest()


@app.get("/health")
def health():
    return {"status": "ok"}

# Generate (enqueue + webhook)
@app.post("/generate-video")
def generate_video(
    prompt: str = Form(...),
    style: str = Form(DEFAULT_STYLE),
    duration: int = Form(8),  # client playback seconds (5–10)
    language: str = Form("English"),
    bg_music: str = Form(""),
):
    final_prompt = build_prompt(prompt, style)
    key = cache_key_for(final_prompt, style, duration)

    # cache hit short-circuit
    cached_url = cache.get(key)
    if cached_url:
        # fabricate a "completed" job for UI consistency
        job_id = f"cache-{hashlib.md5(key.encode()).hexdigest()[:10]}"
        JOBS[job_id] = {"status": "complete", "url": cached_url, "note": "cache"}
        return {"status": "queued", "job_id": job_id, "source": "cache"}

    # if not VADOO_API_KEY:
    #     # if USE_MOCK_ON_FAIL:
    #     #     job_id = f"mock-{hashlib.md5(key.encode()).hexdigest()[:10]}"
    #     #     JOBS[job_id] = {"status": "complete", "url": MOCK_VIDEO_URL, "note": "no_api_key"}
    #     #     cache.set(key, MOCK_VIDEO_URL)
    #     #     return {"status": "queued", "job_id": job_id, "source": "mock"}
    #     # raise HTTPException(status_code=500, detail="Missing VADOO_API_KEY")

    # require public base url for webhook
    if not BACKEND_BASE_URL and not USE_MOCK_ON_FAIL:
        raise HTTPException(status_code=500, detail="BACKEND_BASE_URL not set for webhook")

    v = STYLE_TO_VADOO.get(style, STYLE_TO_VADOO[DEFAULT_STYLE])

    # webhook callback to our backend
    webhook_url = f"{BACKEND_BASE_URL}/webhook/vadoo"
    headers = {"X-API-KEY": VADOO_API_KEY}

    payload = {
        "topic": "Custom",
        "prompt": final_prompt,
        "language": language,
        "voice": v["voice"],
        "theme": v["theme"],
        "style": v["style"],
        "aspect_ratio": v["aspect_ratio"],
        "duration": VADOO_DEFAULT_DURATION,
        "use_ai": "1",
        "include_voiceover": "1",
        # **({"bg_music": bg_music} if bg_music else {}),
    }
    

    try:
        r = requests.post(VADOO_GENERATE_URL, json=payload, headers=headers, timeout=REQUEST_TIMEOUT)
        if r.status_code == 429:
            # client will backoff & retry generate; but still create a local job
            job_id = f"rate-{hashlib.md5(key.encode()).hexdigest()[:10]}"
            JOBS[job_id] = {"status": "error", "url": None, "note": "rate_limited"}
            return {"status": "rate_limited", "message": "Provider rate limit. Please retry."}
        r.raise_for_status()
        vid = r.json().get("vid")
        if not vid:
            raise RuntimeError("No 'vid' in provider response")
        job_id = str(vid)
        JOBS[job_id] = {"status": "queued", "url": None, "note": None}
        # return immediately; webhook will flip to complete
        return {"status": "queued", "job_id": job_id, "source": "provider"}

    except Exception as e:
        if USE_MOCK_ON_FAIL:
            job_id = f"mock-{hashlib.md5(key.encode()).hexdigest()[:10]}"
            JOBS[job_id] = {"status": "complete", "url": MOCK_VIDEO_URL, "note": f"fallback: {e}"}
            cache.set(key, MOCK_VIDEO_URL)
            return {"status": "queued", "job_id": job_id, "source": "mock"}
        raise HTTPException(status_code=500, detail=str(e))

# Webhook endpoint
@app.post("/webhook/vadoo")
async def vadoo_webhook(request: Request):
    """
    Expect JSON like: { "vid": "...", "status": "complete", "url": "https://..." }
    Adjust keys if Vadoo sends different field names.
    """
    try:
        data = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    job_id = str(data.get("vid") or data.get("id") or "")
    status = str(data.get("status") or "").lower()
    url = data.get("url")

    if not job_id:
        raise HTTPException(status_code=400, detail="Missing job id")

    if job_id not in JOBS:
        JOBS[job_id] = {"status": "processing", "url": None, "note": "late_register"}

    if status == "complete" and url:
        JOBS[job_id]["status"] = "complete"
        JOBS[job_id]["url"] = url
    elif status in {"queued", "processing", "running"}:
        JOBS[job_id]["status"] = "processing"
    else:
        JOBS[job_id]["status"] = "error"
        JOBS[job_id]["note"] = f"status={status}"

    # optional: you could backfill cache if you can recover the original prompt key

    return {"ok": True}

# Job status (frontend polls us, not Vadoo)
@app.get("/job-status")
def job_status(job_id: str):
    job = JOBS.get(job_id)
    if not job:
        return {"status": "unknown"}
    return {"status": job["status"], "video_url": job.get("url"), "note": job.get("note")}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=int(os.getenv("PORT", "8000")))
