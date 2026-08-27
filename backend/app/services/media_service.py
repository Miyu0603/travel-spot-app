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

# Instagram and Facebook CDNs serve differently — often not at all — to clients
# that do not look like a browser. scrape_threads already had to do this; the
# image fetcher was left sending httpx's default python-httpx User-Agent.
BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
    "Referer": "https://www.instagram.com/",
}

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


def sample_evenly(urls: list[str], limit: int) -> list[str]:
    """Spread the selection across the whole carousel instead of taking the first N.

    Travel accounts put one spot per slide and the information cards are often
    late in the sequence — taking the first N read slides 1-4 of a 10-slide post
    and missed every card after them.
    """
    if limit <= 0:
        return []
    if len(urls) <= limit:
        return urls
    if limit == 1:
        return [urls[0]]
    step = (len(urls) - 1) / (limit - 1)
    picked: list[str] = []
    for index in range(limit):
        candidate = urls[round(index * step)]
        if candidate not in picked:
            picked.append(candidate)
    return picked


async def fetch_images_as_data_urls(
    urls: list[str], limit: int
) -> tuple[list[str], list[str]]:
    """Download post images, returning (data_urls, failure_reasons).

    A failure is never fatal — a missing image only costs context, while raising
    would lose the whole extraction. But the reason is reported rather than just
    a count: blocked (403), expired (404) and timed out need different fixes, and
    guessing between them has already cost several paid extractions.
    """
    if limit <= 0 or not urls:
        return [], []

    collected: list[str] = []
    failures: list[str] = []
    candidates = sample_evenly(
        [u for u in urls if isinstance(u, str) and u.startswith("http")], limit
    )
    async with httpx.AsyncClient(
        timeout=30, follow_redirects=True, headers=BROWSER_HEADERS
    ) as client:
        for url in candidates:
            if len(collected) >= limit:
                break
            try:
                response = await client.get(url)
            except httpx.TimeoutException:
                failures.append("逾時")
                continue
            except httpx.HTTPError:
                failures.append("連線失敗")
                continue
            if response.status_code != 200:
                failures.append(f"HTTP {response.status_code}")
                continue
            if len(response.content) > MAX_IMAGE_BYTES:
                failures.append("檔案過大")
                continue
            data_url = to_data_url(
                response.content, response.headers.get("content-type", "")
            )
            if data_url:
                collected.append(data_url)
            else:
                failures.append(
                    f"格式不支援（{response.headers.get('content-type', '未知')}）"
                )
    return collected, failures


def summarise_failures(failures: list[str]) -> str:
    """Group reasons so the message names the cause instead of just a count."""
    counts: dict[str, int] = {}
    for reason in failures:
        counts[reason] = counts.get(reason, 0) + 1
    return "、".join(f"{reason} {count} 張" for reason, count in counts.items())


def frames_to_data_urls(frames: list[str]) -> list[str]:
    """ffmpeg already gives us base64 JPEG; wrap them as data URLs."""
    return [f"data:image/jpeg;base64,{frame}" for frame in frames]
