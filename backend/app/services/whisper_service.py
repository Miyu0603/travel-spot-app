"""
Whisper Service: Transcribes video/audio content using OpenAI Whisper API.
"""

import httpx
import tempfile
import os

from app.config import settings


async def transcribe_video(video_url: str) -> str:
    """Download a video and transcribe it using OpenAI Whisper API."""
    if not settings.openai_api_key:
        return ""

    # Download the video/audio
    async with httpx.AsyncClient(timeout=300) as client:
        response = await client.get(video_url)
        if response.status_code != 200:
            return ""

        # Save to temp file
        suffix = ".mp4"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(response.content)
            tmp_path = tmp.name

    try:
        # Send to Whisper API
        async with httpx.AsyncClient(timeout=120) as client:
            with open(tmp_path, "rb") as audio_file:
                response = await client.post(
                    "https://api.openai.com/v1/audio/transcriptions",
                    headers={"Authorization": f"Bearer {settings.openai_api_key}"},
                    files={"file": ("audio.mp4", audio_file, "video/mp4")},
                    data={"model": "whisper-1", "language": "zh"},
                )

            if response.status_code != 200:
                return ""

            return response.json().get("text", "")
    finally:
        os.unlink(tmp_path)
