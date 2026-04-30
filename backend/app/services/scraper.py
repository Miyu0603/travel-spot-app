"""
Scraper service: uses Apify to fetch content from IG/FB, 
and Threads API for Threads posts.
"""

import re
import httpx

from app.config import settings
from app.models.source import PlatformEnum


def detect_platform(url: str) -> PlatformEnum:
    """Detect which social media platform a URL belongs to."""
    if "instagram.com" in url:
        return PlatformEnum.INSTAGRAM
    elif "facebook.com" in url or "fb.com" in url:
        return PlatformEnum.FACEBOOK
    elif "threads.net" in url:
        return PlatformEnum.THREADS
    return PlatformEnum.OTHER


async def scrape_instagram(url: str) -> dict:
    """Scrape an Instagram post using Apify."""
    if not settings.apify_api_token:
        return {"success": False, "error": "Apify API token not configured"}

    api_url = "https://api.apify.com/v2/acts/apify~instagram-scraper/run-sync-get-dataset-items"

    async with httpx.AsyncClient(timeout=120) as client:
        response = await client.post(
            api_url,
            params={"token": settings.apify_api_token},
            json={
                "directUrls": [url],
                "resultsType": "posts",
                "resultsLimit": 1,
            },
        )

        if response.status_code not in (200, 201):
            return {"success": False, "error": f"Apify returned status {response.status_code}"}

        data = response.json()
        if not data:
            return {"success": False, "error": "No data returned from Apify"}

        post = data[0]
        return {
            "success": True,
            "text": post.get("caption", ""),
            "images": [post["displayUrl"]] if post.get("displayUrl") else [],
            "video_url": post.get("videoUrl"),
            "timestamp": post.get("timestamp"),
        }


async def scrape_facebook(url: str) -> dict:
    """Scrape a Facebook post using Apify."""
    if not settings.apify_api_token:
        return {"success": False, "error": "Apify API token not configured"}

    api_url = "https://api.apify.com/v2/acts/apify~facebook-posts-scraper/run-sync-get-dataset-items"

    async with httpx.AsyncClient(timeout=120) as client:
        response = await client.post(
            api_url,
            params={"token": settings.apify_api_token},
            json={
                "startUrls": [{"url": url}],
                "resultsLimit": 1,
            },
        )

        if response.status_code not in (200, 201):
            return {"success": False, "error": f"Apify returned status {response.status_code}"}

        data = response.json()
        if not data:
            return {"success": False, "error": "No data returned from Apify"}

        post = data[0]
        return {
            "success": True,
            "text": post.get("text", ""),
            "images": post.get("images", []),
            "video_url": post.get("videoUrl"),
        }


async def scrape_threads(url: str) -> dict:
    """Scrape a Threads post by fetching Open Graph meta tags from the page."""
    async with httpx.AsyncClient(
        timeout=30,
        follow_redirects=True,
        headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        },
    ) as client:
        try:
            response = await client.get(url)
            if response.status_code != 200:
                return {"success": False, "error": f"Failed to fetch Threads page (status {response.status_code})"}

            html = response.text

            # Extract Open Graph description (contains post text)
            og_desc = _extract_meta(html, "og:description") or ""
            og_title = _extract_meta(html, "og:title") or ""
            og_image = _extract_meta(html, "og:image") or ""

            text = og_desc or og_title
            if not text:
                return {"success": False, "error": "Could not extract text from Threads post. Please paste content manually."}

            return {
                "success": True,
                "text": text,
                "images": [og_image] if og_image else [],
                "video_url": None,
            }
        except httpx.TimeoutException:
            return {"success": False, "error": "Threads page request timed out"}


def _extract_meta(html: str, property_name: str) -> str | None:
    """Extract content from an Open Graph meta tag."""
    pattern = rf'<meta\s+(?:property|name)="{re.escape(property_name)}"\s+content="([^"]*)"'
    match = re.search(pattern, html)
    if not match:
        # Try reversed attribute order
        pattern = rf'<meta\s+content="([^"]*)"\s+(?:property|name)="{re.escape(property_name)}"'
        match = re.search(pattern, html)
    return match.group(1) if match else None


async def scrape_url(url: str) -> dict:
    """Route URL to the appropriate scraper."""
    platform = detect_platform(url)

    if platform == PlatformEnum.INSTAGRAM:
        return await scrape_instagram(url)
    elif platform == PlatformEnum.FACEBOOK:
        return await scrape_facebook(url)
    elif platform == PlatformEnum.THREADS:
        return await scrape_threads(url)
    else:
        return {"success": False, "error": "Unsupported platform"}
