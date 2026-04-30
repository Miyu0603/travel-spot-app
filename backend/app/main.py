from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import engine, Base
from app.routers import spots, sources

# Create database tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Travel Spot App",
    description="從社群貼文萃取旅遊景點資訊的 API",
    version="0.1.0",
)

import os

allowed_origins = os.getenv(
    "CORS_ORIGINS",
    "http://localhost:3000,http://localhost:3001"
).split(",")

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
    return {"message": "Travel Spot App API is running"}
