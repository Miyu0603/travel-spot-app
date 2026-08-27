"""
Geo Service: fills in authoritative location data for a spot.

Google Places is the primary source — it knows the real address, opening hours
and place link, none of which the LLM can be trusted to remember. Nominatim
stays as a no-API-key fallback that supplies coordinates only; it must never be
allowed to overwrite address or hours, because it has neither.
"""

import asyncio
import urllib.parse

import httpx

from app.config import settings

PLACES_SEARCH_URL = "https://places.googleapis.com/v1/places:searchText"

# Only the fields we store, so we are not billed for data we discard.
PLACES_FIELD_MASK = ",".join(
    (
        "places.formattedAddress",
        "places.location",
        "places.googleMapsUri",
        "places.regularOpeningHours.weekdayDescriptions",
        "places.nationalPhoneNumber",
        "places.websiteUri",
    )
)

# Nominatim's usage policy allows at most one request per second.
NOMINATIM_MIN_INTERVAL = 1.0


def _search_url(query: str) -> str:
    return f"https://www.google.com/maps/search/{urllib.parse.quote(query)}"


async def lookup_google_place(query: str) -> dict:
    """Look a spot up in Google Places. Returns {} when unavailable."""
    if not settings.google_maps_api_key or not query:
        return {}

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.post(
                PLACES_SEARCH_URL,
                headers={
                    "Content-Type": "application/json",
                    "X-Goog-Api-Key": settings.google_maps_api_key,
                    "X-Goog-FieldMask": PLACES_FIELD_MASK,
                },
                json={"textQuery": query, "languageCode": "zh-TW", "maxResultCount": 1},
            )
    except httpx.HTTPError:
        return {}

    if response.status_code != 200:
        # 403 usually means "Places API (New)" is not enabled on the project.
        # Falling back keeps extraction working instead of failing outright.
        return {}

    try:
        places = response.json().get("places") or []
    except ValueError:
        return {}
    if not places:
        return {}

    place = places[0]
    found: dict = {"geo_source": "google_places"}

    if place.get("formattedAddress"):
        found["address"] = place["formattedAddress"]

    location = place.get("location") or {}
    if "latitude" in location and "longitude" in location:
        found["latitude"] = float(location["latitude"])
        found["longitude"] = float(location["longitude"])

    if place.get("googleMapsUri"):
        found["google_maps_url"] = place["googleMapsUri"]

    weekdays = (place.get("regularOpeningHours") or {}).get("weekdayDescriptions") or []
    if weekdays:
        found["business_hours"] = "；".join(weekdays)

    extras = []
    if place.get("nationalPhoneNumber"):
        extras.append(f"電話：{place['nationalPhoneNumber']}")
    if place.get("websiteUri"):
        extras.append(f"官網：{place['websiteUri']}")
    if extras:
        found["place_extras"] = "；".join(extras)

    return found


async def probe_places_access() -> tuple[bool, str]:
    """One diagnostic call, so a misconfigured project reports itself.

    lookup_google_place() deliberately swallows failures to keep extraction
    running, which makes "API not enabled" indistinguishable from "no such
    place". Tools that need the difference ask here first.
    """
    if not settings.google_maps_api_key:
        return False, "未設定 GOOGLE_MAPS_API_KEY"

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.post(
                PLACES_SEARCH_URL,
                headers={
                    "Content-Type": "application/json",
                    "X-Goog-Api-Key": settings.google_maps_api_key,
                    "X-Goog-FieldMask": "places.formattedAddress",
                },
                json={"textQuery": "台北101", "languageCode": "zh-TW", "maxResultCount": 1},
            )
    except httpx.HTTPError as exc:
        return False, f"無法連線到 Google Places：{exc}"

    if response.status_code == 200:
        return True, "Google Places 可正常使用"
    if response.status_code == 403:
        # "key restricted" and "service not enabled" need different fixes, and
        # Google distinguishes them in the error body even though both are 403.
        reason, project = _denial_details(response)
        where = f"（專案 {project}）" if project else ""
        if reason == "API_KEY_SERVICE_BLOCKED":
            return False, (
                f"API key 的限制清單不含 Places API (New){where}。"
                "請到 Google Cloud Console → 憑證 → 該金鑰 → API 限制，"
                "把「Places API (New)」加入允許清單。注意它與舊版「Places API」"
                "是不同項目。"
            )
        if reason == "SERVICE_DISABLED":
            return False, (
                f"專案尚未啟用 Places API (New){where}。"
                "請到 Google Cloud Console → API 程式庫啟用它。"
            )
        return False, f"Google 拒絕存取（403，{reason or '原因不明'}）{where}"
    if response.status_code == 400:
        return False, "請求被拒（400），API key 可能無效"
    if response.status_code == 429:
        return False, "Google Places 配額已用盡（429）"
    return False, f"Google Places 回應異常（HTTP {response.status_code}）"


def _denial_details(response: httpx.Response) -> tuple[str, str]:
    """Pull the machine-readable reason and project number out of a 403 body."""
    try:
        details = response.json()["error"]["details"]
    except (ValueError, KeyError, TypeError):
        return "", ""
    for detail in details:
        if not isinstance(detail, dict) or "reason" not in detail:
            continue
        consumer = (detail.get("metadata") or {}).get("consumer", "")
        return detail["reason"], consumer.split("/")[-1] if consumer else ""
    return "", ""


async def lookup_nominatim(query: str) -> dict:
    """Free OpenStreetMap geocoding. Coordinates only — it has no hours."""
    if not query:
        return {}
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(
                "https://nominatim.openstreetmap.org/search",
                params={"q": query, "format": "json", "limit": 1, "accept-language": "zh-TW"},
                headers={"User-Agent": "TravelSpotApp/1.0"},
            )
        if response.status_code != 200:
            return {}
        data = response.json()
        if not data:
            return {}
        return {
            "geo_source": "nominatim",
            "latitude": float(data[0]["lat"]),
            "longitude": float(data[0]["lon"]),
        }
    except Exception:
        # Coordinates are optional; the Maps search URL is still useful.
        return {}


async def enrich_spot_with_geo(spot_name: str, address: str = "") -> dict:
    """Best available location data for one spot."""
    query = f"{spot_name} {address}".strip()
    if not query:
        return {}

    found = await lookup_google_place(query)
    if found:
        found.setdefault("google_maps_url", _search_url(query))
        return found

    fallback = await lookup_nominatim(query)
    fallback["google_maps_url"] = _search_url(query)
    return fallback


def merge_geo_into_spot(spot: dict, geo: dict) -> dict:
    """Apply lookup results, letting the better source win per field.

    Google Places outranks whatever the LLM guessed for address and hours.
    Nominatim never touches those — it only knows coordinates — so its results
    must not be allowed to blank out the LLM's guesses.
    """
    if not geo:
        return spot

    authoritative = geo.get("geo_source") == "google_places"

    for key in ("latitude", "longitude", "google_maps_url"):
        if geo.get(key) not in (None, ""):
            spot[key] = geo[key]

    if authoritative:
        for key in ("address", "business_hours"):
            if geo.get(key):
                spot[key] = geo[key]
        extras = geo.get("place_extras")
        if extras and extras not in (spot.get("notes") or ""):
            spot["notes"] = f"{spot['notes']}；{extras}" if spot.get("notes") else extras

    return spot


async def enrich_spots(spots: list[dict]) -> list[dict]:
    """Enrich a list of spots with geo data."""
    enriched = []
    for index, spot in enumerate(spots):
        if index and not settings.google_maps_api_key:
            # Only the Nominatim path needs throttling; Places has no such rule.
            await asyncio.sleep(NOMINATIM_MIN_INTERVAL)
        geo = await enrich_spot_with_geo(spot.get("title", ""), spot.get("address", ""))
        enriched.append(merge_geo_into_spot(spot, geo))
    return enriched
