"""
Geo Service: Enriches spot data with Google Maps URLs
and coordinates via free Nominatim geocoding.
"""

import urllib.parse

import httpx


async def enrich_spot_with_geo(spot_name: str, address: str = "") -> dict:
    """Enrich a spot with a Google Maps search URL and coordinates from Nominatim."""
    query = f"{spot_name} {address}".strip()
    if not query:
        return {}

    # Generate Google Maps search URL (no API key needed)
    maps_url = f"https://www.google.com/maps/search/{urllib.parse.quote(query)}"

    result = {
        "google_maps_url": maps_url,
    }

    # Try free Nominatim geocoding for coordinates
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(
                "https://nominatim.openstreetmap.org/search",
                params={
                    "q": query,
                    "format": "json",
                    "limit": 1,
                    "accept-language": "zh-TW",
                },
                headers={"User-Agent": "TravelSpotApp/1.0"},
            )
            if response.status_code == 200:
                data = response.json()
                if data:
                    result["latitude"] = float(data[0]["lat"])
                    result["longitude"] = float(data[0]["lon"])
    except Exception:
        pass  # Coordinates are optional; Maps URL is still useful

    return result


async def enrich_spots(spots: list[dict]) -> list[dict]:
    """Enrich a list of spots with geo data."""
    enriched = []
    for spot in spots:
        geo = await enrich_spot_with_geo(spot.get("title", ""), spot.get("address", ""))
        if geo:
            spot.update({k: v for k, v in geo.items() if v})
        enriched.append(spot)
    return enriched
