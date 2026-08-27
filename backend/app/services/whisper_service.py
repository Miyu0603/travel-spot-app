"""
Whisper Service: Transcribes video/audio content using OpenAI Whisper API.
"""

import os
import tempfile

import httpx

from app.config import settings

# Whisper rejects uploads above 25 MB. Checking up front turns a confusing API
# error into a message that says what to do about it.
MAX_UPLOAD_BYTES = 25 * 1024 * 1024


class TranscriptionError(Exception):
    """Transcription failed. Not fatal — the caption may still carry the spots."""


async def download_video(video_url: str, destination: str) -> int:
    """Stream a video to disk. Returns its size in bytes.

    Streamed rather than held in memory: Render's free instance has 512 MB and a
    long Reel can be a sizeable fraction of that.
    """
    written = 0
    async with httpx.AsyncClient(timeout=300, follow_redirects=True) as client:
        async with client.stream("GET", video_url) as response:
            if response.status_code != 200:
                raise TranscriptionError(f"影片下載失敗（HTTP {response.status_code}）")
            with open(destination, "wb") as handle:
                async for chunk in response.aiter_bytes(chunk_size=1 << 16):
                    written += len(chunk)
                    if written > MAX_UPLOAD_BYTES:
                        raise TranscriptionError(
                            "影片超過 25MB，Whisper 無法處理，請改用手動貼上內容"
                        )
                    handle.write(chunk)
    if not written:
        raise TranscriptionError("影片內容是空的")
    return written


async def transcribe_file(path: str) -> str:
    """Transcribe an already-downloaded video with the OpenAI Whisper API.

    Split from the download so the caller can reuse one local copy for both
    transcription and frame extraction instead of fetching the video twice.
    """
    if not settings.openai_api_key:
        raise TranscriptionError("尚未設定 OpenAI API key，無法轉錄影片")

    try:
        async with httpx.AsyncClient(timeout=180) as client:
            with open(path, "rb") as audio_file:
                response = await client.post(
                    "https://api.openai.com/v1/audio/transcriptions",
                    headers={"Authorization": f"Bearer {settings.openai_api_key}"},
                    files={"file": ("audio.mp4", audio_file, "video/mp4")},
                    # No language is pinned: hard-coding "zh" turned Japanese
                    # narration into nonsense, and this app is full of Japan.
                    data={"model": "whisper-1"},
                )

        if response.status_code == 429:
            raise TranscriptionError("轉錄服務額度已用盡或請求過於頻繁")
        if response.status_code != 200:
            raise TranscriptionError(f"轉錄服務回應異常（HTTP {response.status_code}）")

        try:
            return response.json().get("text", "")
        except ValueError as exc:
            raise TranscriptionError("轉錄服務回傳的內容無法解析") from exc
    except httpx.HTTPError as exc:
        raise TranscriptionError("無法連線到轉錄服務，請稍後再試") from exc


async def transcribe_video(video_url: str) -> str:
    """Download and transcribe in one step, for callers that need nothing else."""
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
        tmp_path = tmp.name
    try:
        await download_video(video_url, tmp_path)
        return await transcribe_file(tmp_path)
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
