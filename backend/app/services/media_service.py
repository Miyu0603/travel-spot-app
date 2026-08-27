"""
Media Service: turns a post's remote images into data URLs for the vision model.

Instagram and Facebook serve images from signed CDN URLs that expire, so they
are fetched here and inlined rather than handed to OpenAI as links.
"""

import base64

import httpx

# Comfortably above a normal post photo, low enough that one oversized image
# cannot blow up the request body.
MAX_IMAGE_BYTES = 5 * 1024 * 1024

_ALLOWED_TYPES = {
    "image/jpeg": "jpeg",
    "image/jpg": "jpeg",
    "image/png": "png",
    "image/webp": "webp",
}


def to_data_url(raw: bytes, content_type: str) -> str | None:
    kind = _ALLOWED_TYPES.get(content_type.split(";")[0].strip().lower())
    if not kind:
        return None
    return f"data:image/{kind};base64,{base64.b64encode(raw).decode('ascii')}"


async def fetch_images_as_data_urls(
    urls: list[str], limit: int
) -> tuple[list[str], int]:
    """Download post images, returning (data_urls, failed_count).

    A failure is never fatal — a missing image only costs context, while raising
    would lose the whole extraction. But it is reported: when a post keeps its
    spots on the images and every image fails, silently returning fewer results
    looks exactly like a post that had less in it.
    """
    if limit <= 0 or not urls:
        return [], 0

    collected: list[str] = []
    failed = 0
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        for url in urls:
            if len(collected) >= limit:
                break
            if not isinstance(url, str) or not url.startswith("http"):
                continue
            try:
                response = await client.get(url)
            except httpx.HTTPError:
                failed += 1
                continue
            if response.status_code != 200 or len(response.content) > MAX_IMAGE_BYTES:
                failed += 1
                continue
            data_url = to_data_url(
                response.content, response.headers.get("content-type", "")
            )
            if data_url:
                collected.append(data_url)
            else:
                failed += 1
    return collected, failed


def frames_to_data_urls(frames: list[str]) -> list[str]:
    """ffmpeg already gives us base64 JPEG; wrap them as data URLs."""
    return [f"data:image/jpeg;base64,{frame}" for frame in frames]
