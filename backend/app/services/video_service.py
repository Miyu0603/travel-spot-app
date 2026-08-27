"""
Video Service: pulls still frames out of a video so the vision model can read
text that is only ever shown on screen.

Plenty of travel posts are a silent slideshow of captions — Whisper hears
nothing there, and without frames the whole video is invisible to extraction.

ffmpeg is not present on Render's Python runtime, so the binary comes from the
imageio-ffmpeg wheel rather than the system. ffprobe is not in that wheel, so
the duration is read from ffmpeg's own stderr banner instead.
"""

import asyncio
import base64
import os
import re
import subprocess
import tempfile

from app.config import settings

_DURATION_RE = re.compile(r"Duration:\s*(\d+):(\d\d):(\d\d(?:\.\d+)?)")


class FrameExtractionError(Exception):
    """Frames could not be extracted. Not fatal — captions and audio remain."""


def _ffmpeg_binary() -> str:
    try:
        import imageio_ffmpeg
    except ImportError as exc:
        raise FrameExtractionError("未安裝 imageio-ffmpeg，無法擷取影片畫面") from exc
    return imageio_ffmpeg.get_ffmpeg_exe()


def probe_duration(ffmpeg: str, video_path: str) -> float:
    """Seconds of video, parsed from ffmpeg's banner (the wheel has no ffprobe)."""
    result = subprocess.run(
        [ffmpeg, "-i", video_path], capture_output=True, timeout=60
    )
    match = _DURATION_RE.search(result.stderr.decode("utf-8", "replace"))
    if not match:
        raise FrameExtractionError("無法讀取影片長度")
    hours, minutes, seconds = match.groups()
    return int(hours) * 3600 + int(minutes) * 60 + float(seconds)


def has_audio_stream(video_path: str) -> bool:
    """Whether the file carries any audio.

    Caption-card videos are commonly silent, and Whisper rejects a file with no
    audio with a bare HTTP 400 — a paid request that could never succeed, plus a
    failure warning that makes a working extraction look broken.
    """
    try:
        ffmpeg = _ffmpeg_binary()
    except FrameExtractionError:
        return True  # cannot tell; let Whisper decide rather than skip wrongly
    result = subprocess.run([ffmpeg, "-i", video_path], capture_output=True, timeout=60)
    return "Audio:" in result.stderr.decode("utf-8", "replace")


def _extract_frames_sync(video_path: str, frame_count: int) -> list[str]:
    """Frames as base64 JPEG, one from the middle of each equal slice.

    Sampling by timestamp rather than with ffmpeg's `thumbnail` filter: that
    filter batches by frame count, so without knowing the length up front it
    silently returns far fewer frames than asked for.
    """
    ffmpeg = _ffmpeg_binary()
    duration = probe_duration(ffmpeg, video_path)
    if duration <= 0:
        raise FrameExtractionError("影片長度為零")

    frames: list[str] = []
    with tempfile.TemporaryDirectory() as workdir:
        for index in range(frame_count):
            timestamp = duration * (index + 0.5) / frame_count
            output = os.path.join(workdir, f"frame_{index}.jpg")
            result = subprocess.run(
                [
                    ffmpeg, "-y",
                    "-ss", f"{timestamp:.3f}",
                    "-i", video_path,
                    "-frames:v", "1",
                    "-vf", "scale=768:-2",
                    "-q:v", "3",
                    output,
                ],
                capture_output=True,
                timeout=60,
            )
            if result.returncode != 0 or not os.path.exists(output):
                continue  # a single unreadable timestamp should not lose the rest
            with open(output, "rb") as handle:
                frames.append(base64.b64encode(handle.read()).decode("ascii"))

    if not frames:
        raise FrameExtractionError("無法從影片擷取任何畫面")
    return frames


async def extract_frames(video_path: str, frame_count: int | None = None) -> list[str]:
    """Base64 JPEG frames from a local video file. Empty list when disabled."""
    count = settings.video_frame_count if frame_count is None else frame_count
    if count <= 0:
        return []
    # ffmpeg is a blocking subprocess; keep it off the event loop.
    return await asyncio.to_thread(_extract_frames_sync, video_path, count)
