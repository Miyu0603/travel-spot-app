from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import settings
from app.database import engine, Base
from app.routers import spots, sources

# Create database tables
Base.metadata.create_all(bind=engine)

# Bumped whenever deployed behaviour changes, so / can prove which build is live.
APP_VERSION = "0.2.0"

app = FastAPI(
    title="Travel Spot App",
    description="從社群貼文萃取旅遊景點資訊的 API",
    version=APP_VERSION,
)

allowed_origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]

# API key authentication middleware
API_SECRET = settings.api_secret


class ApiKeyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Skip auth for root, docs, OPTIONS (CORS preflight)
        if request.url.path in ("/", "/docs", "/openapi.json") or request.method == "OPTIONS":
            return await call_next(request)
        # Skip if no secret configured (local dev)
        if not API_SECRET:
            return await call_next(request)
        token = request.headers.get("X-API-Key", "")
        if token != API_SECRET:
            return JSONResponse(status_code=401, content={"detail": "Unauthorized"})
        return await call_next(request)


# Order matters: add_middleware wraps outwards, so the LAST one added runs first.
# CORS must be outermost, otherwise the 401 short-circuits before CORS headers are
# attached and the browser blocks the response — the frontend then sees a generic
# network failure instead of "your password expired".
app.add_middleware(ApiKeyMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(spots.router, prefix="/api/spots", tags=["景點"])
app.include_router(sources.router, prefix="/api/sources", tags=["來源"])


@app.get("/")
def root():
    """Health check that also reports which capabilities are actually live.

    Without this there is no way to tell a stale deploy from a missing env var:
    both make Places and vision quietly fall back, and the only visible symptom
    is thinner results. Only booleans are exposed — never the keys themselves.
    """
    return {
        "message": "Travel Spot App API is running",
        "version": APP_VERSION,
        "capabilities": {
            "places": bool(settings.google_maps_api_key),
            "ai_extraction": bool(settings.openai_api_key),
            "scraping": bool(settings.apify_api_token),
            "auth_required": bool(settings.api_secret),
            "post_images": settings.max_post_images,
            "video_frames": settings.video_frame_count,
        },
    }
