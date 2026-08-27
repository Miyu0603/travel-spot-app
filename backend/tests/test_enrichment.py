"""Tests for the enrichment pipeline: Places lookup, media handling, frames.

Runs standalone with no test framework. No paid API is ever called — Places and
Whisper are driven with fake HTTP responses, and the video test generates its own
clip with the bundled ffmpeg.

    python tests/test_enrichment.py
"""

import asyncio
import base64
import os
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx  # noqa: E402

from app.config import settings  # noqa: E402
from app.services import geo_service, media_service  # noqa: E402
from app.services.geo_service import _denial_details  # noqa: E402
from app.services.ai_extractor import _user_content  # noqa: E402
from app.services.geo_service import merge_geo_into_spot  # noqa: E402
from app.services.media_service import to_data_url  # noqa: E402
from app.services.video_service import extract_frames, probe_duration  # noqa: E402
from app.services.whisper_service import (  # noqa: E402
    MAX_UPLOAD_BYTES,
    TranscriptionError,
    download_video,
)

PLACES_HIT = {
    "places": [
        {
            "formattedAddress": "日本〒802-0000 福岡県北九州市八幡東区大字尾倉1481-1",
            "location": {"latitude": 33.85, "longitude": 130.79},
            "googleMapsUri": "https://maps.google.com/?cid=123",
            "regularOpeningHours": {
                "weekdayDescriptions": ["星期一: 休息", "星期二: 10:00 – 22:00"]
            },
            "nationalPhoneNumber": "093-123-4567",
            "websiteUri": "https://example.jp",
        }
    ]
}


def fake_transport(status: int, payload: dict | None = None):
    """Patch httpx.AsyncClient so nothing leaves the machine."""

    class FakeClient:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, *a, **k):
            return httpx.Response(
                status, json=payload or {}, request=httpx.Request("POST", "https://x")
            )

        async def get(self, *a, **k):
            return httpx.Response(
                status, json=payload or {}, request=httpx.Request("GET", "https://x")
            )

    return FakeClient


# --- Google Places lookup ---

def test_places_hit_returns_every_field_we_store():
    settings.google_maps_api_key = "fake-key"
    geo_service.httpx.AsyncClient = fake_transport(200, PLACES_HIT)
    found = asyncio.run(geo_service.lookup_google_place("皿倉山"))
    assert found["geo_source"] == "google_places"
    assert "福岡" in found["address"]
    assert found["latitude"] == 33.85 and found["longitude"] == 130.79
    assert found["google_maps_url"] == "https://maps.google.com/?cid=123"
    assert "星期二: 10:00 – 22:00" in found["business_hours"]
    assert "093-123-4567" in found["place_extras"]


def test_places_returns_nothing_without_a_key():
    settings.google_maps_api_key = ""
    assert asyncio.run(geo_service.lookup_google_place("皿倉山")) == {}


def test_places_api_not_enabled_is_not_fatal():
    """A 403 (Places API New not enabled) must degrade, not break extraction."""
    settings.google_maps_api_key = "fake-key"
    geo_service.httpx.AsyncClient = fake_transport(403, {"error": "denied"})
    assert asyncio.run(geo_service.lookup_google_place("皿倉山")) == {}


def test_places_empty_result_is_handled():
    settings.google_maps_api_key = "fake-key"
    geo_service.httpx.AsyncClient = fake_transport(200, {"places": []})
    assert asyncio.run(geo_service.lookup_google_place("不存在的地方")) == {}


def _denial_body(reason: str) -> dict:
    return {
        "error": {
            "code": 403,
            "status": "PERMISSION_DENIED",
            "details": [
                {
                    "@type": "type.googleapis.com/google.rpc.ErrorInfo",
                    "reason": reason,
                    "metadata": {"consumer": "projects/118443993735"},
                }
            ],
        }
    }


def test_denial_details_extracts_reason_and_project():
    response = httpx.Response(
        403, json=_denial_body("API_KEY_SERVICE_BLOCKED"),
        request=httpx.Request("POST", "https://x"),
    )
    assert _denial_details(response) == ("API_KEY_SERVICE_BLOCKED", "118443993735")


def test_denial_details_survives_an_unparseable_body():
    response = httpx.Response(403, text="not json", request=httpx.Request("POST", "https://x"))
    assert _denial_details(response) == ("", "")


def test_blocked_key_and_disabled_service_give_different_instructions():
    """Both are 403 but need different fixes; a generic message sends the user
    to the wrong screen."""
    settings.google_maps_api_key = "fake-key"

    geo_service.httpx.AsyncClient = fake_transport(403, _denial_body("API_KEY_SERVICE_BLOCKED"))
    ok, blocked = asyncio.run(geo_service.probe_places_access())
    assert not ok and "限制清單" in blocked and "118443993735" in blocked

    geo_service.httpx.AsyncClient = fake_transport(403, _denial_body("SERVICE_DISABLED"))
    ok, disabled = asyncio.run(geo_service.probe_places_access())
    assert not ok and "尚未啟用" in disabled
    assert blocked != disabled


def test_probe_reports_success_when_places_works():
    settings.google_maps_api_key = "fake-key"
    geo_service.httpx.AsyncClient = fake_transport(200, PLACES_HIT)
    ok, message = asyncio.run(geo_service.probe_places_access())
    assert ok and "可正常使用" in message


def test_probe_without_a_key_says_so():
    settings.google_maps_api_key = ""
    ok, message = asyncio.run(geo_service.probe_places_access())
    assert not ok and "GOOGLE_MAPS_API_KEY" in message


# --- merge policy: who is allowed to overwrite what ---

def test_places_overrides_the_models_guesses():
    spot = {"title": "皿倉山", "address": "模型猜的地址", "business_hours": "模型猜的時間"}
    merged = merge_geo_into_spot(spot, {
        "geo_source": "google_places",
        "address": "真實地址",
        "business_hours": "真實時間",
        "latitude": 1.0, "longitude": 2.0,
    })
    assert merged["address"] == "真實地址"
    assert merged["business_hours"] == "真實時間"


def test_nominatim_never_blanks_address_or_hours():
    """Nominatim knows neither field; letting it through would delete good data."""
    spot = {"title": "x", "address": "模型猜的地址", "business_hours": "11:00-21:00"}
    merged = merge_geo_into_spot(spot, {
        "geo_source": "nominatim", "latitude": 1.0, "longitude": 2.0,
    })
    assert merged["address"] == "模型猜的地址"
    assert merged["business_hours"] == "11:00-21:00"
    assert merged["latitude"] == 1.0


def test_place_extras_are_appended_to_notes_once():
    spot = {"title": "x", "notes": "需預約"}
    geo = {"geo_source": "google_places", "place_extras": "電話：093"}
    merged = merge_geo_into_spot(dict(spot), geo)
    assert merged["notes"] == "需預約；電話：093"
    # Running enrichment twice must not duplicate the suffix
    assert merge_geo_into_spot(merged, geo)["notes"] == "需預約；電話：093"


def test_empty_geo_leaves_the_spot_untouched():
    spot = {"title": "x", "address": "a"}
    assert merge_geo_into_spot(dict(spot), {}) == spot


# --- images ---

def test_supported_image_types_become_data_urls():
    for content_type, marker in [
        ("image/jpeg", "jpeg"), ("image/png", "png"),
        ("image/webp", "webp"), ("image/jpeg; charset=binary", "jpeg"),
    ]:
        url = to_data_url(b"\xff\xd8fake", content_type)
        assert url and url.startswith(f"data:image/{marker};base64,")


def test_unsupported_image_type_is_rejected():
    assert to_data_url(b"GIF89a", "image/gif") is None
    assert to_data_url(b"<html>", "text/html") is None


def test_failed_images_are_skipped_but_counted():
    """Reported, not swallowed: when a post keeps its spots on the images and
    every one fails, a thin result must not look like a thin post."""
    media_service.httpx.AsyncClient = fake_transport(404)
    collected, failed = asyncio.run(
        media_service.fetch_images_as_data_urls(["https://x/a.jpg", "https://x/b.jpg"], 4)
    )
    assert collected == [] and failed == 2


def test_image_fetching_can_be_disabled():
    assert asyncio.run(media_service.fetch_images_as_data_urls(["https://x/a.jpg"], 0)) == ([], 0)


def test_frames_are_wrapped_as_data_urls():
    assert media_service.frames_to_data_urls(["QUJD"]) == ["data:image/jpeg;base64,QUJD"]


# --- carousel media collection ---

def test_carousel_slides_are_all_collected_in_order():
    """The spots live one per slide; reading only displayUrl loses all but the cover."""
    from app.services.scraper import _collect_media

    images, video = _collect_media({
        "displayUrl": "https://cover.jpg",
        "childPosts": [
            {"displayUrl": "https://s1.jpg"},
            {"displayUrl": "https://s2.jpg"},
            {"displayUrl": "https://s3.jpg", "videoUrl": "https://v.mp4"},
        ],
    })
    assert images == [
        "https://s1.jpg", "https://s2.jpg", "https://s3.jpg", "https://cover.jpg",
    ]
    assert video == "https://v.mp4"


def test_images_array_shape_is_also_supported():
    """Apify has moved the slides between fields across actor versions."""
    from app.services.scraper import _collect_media

    images, _ = _collect_media({
        "displayUrl": "https://cover.jpg",
        "images": ["https://a.jpg", "https://b.jpg"],
    })
    assert images == ["https://a.jpg", "https://b.jpg", "https://cover.jpg"]


def test_duplicate_and_invalid_urls_are_dropped():
    from app.services.scraper import _collect_media

    images, _ = _collect_media({
        "displayUrl": "https://a.jpg",
        "images": ["https://a.jpg", None, 42, "not-a-url", "https://b.jpg"],
    })
    # De-duplication keeps the first occurrence, so the cover does not jump to
    # the end just because it also appears in the slide list.
    assert images == ["https://a.jpg", "https://b.jpg"]


def test_post_level_video_still_wins_when_present():
    from app.services.scraper import _collect_media

    _, video = _collect_media({
        "videoUrl": "https://main.mp4",
        "childPosts": [{"videoUrl": "https://child.mp4"}],
    })
    assert video == "https://main.mp4"


def test_empty_post_yields_nothing():
    from app.services.scraper import _collect_media

    assert _collect_media({}) == ([], None)


# --- the multimodal message ---

def test_text_only_post_sends_one_text_part():
    settings.max_post_images = 4
    content = _user_content("貼文內容", [])
    assert len(content) == 1 and content[0]["type"] == "text"
    assert "<post>" in content[0]["text"]


def test_images_are_attached_after_the_text():
    settings.max_post_images = 4
    content = _user_content("貼文", ["data:image/jpeg;base64,a", "data:image/jpeg;base64,b"])
    assert [part["type"] for part in content] == ["text", "image_url", "image_url"]


def test_image_count_is_capped_to_control_cost():
    settings.max_post_images = 2
    content = _user_content("貼文", [f"data:image/jpeg;base64,{i}" for i in range(10)])
    assert sum(1 for part in content if part["type"] == "image_url") == 2
    settings.max_post_images = 4


# --- whisper guards ---

def test_video_larger_than_whisper_allows_is_rejected_early():
    """Whisper 400s on >25MB; catching it here explains what to do instead."""
    oversized = b"\0" * (MAX_UPLOAD_BYTES + 1024)

    class FakeStream:
        status_code = 200

        async def aiter_bytes(self, chunk_size=0):
            for start in range(0, len(oversized), 1 << 16):
                yield oversized[start:start + (1 << 16)]

    class FakeClient:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        def stream(self, *a, **k):
            stream = FakeStream()

            class Ctx:
                async def __aenter__(self):
                    return stream

                async def __aexit__(self, *a):
                    return False

            return Ctx()

    import app.services.whisper_service as ws
    ws.httpx.AsyncClient = FakeClient
    destination = tempfile.mktemp(suffix=".mp4")
    try:
        asyncio.run(download_video("https://x/v.mp4", destination))
        raise AssertionError("expected the size guard to fire")
    except TranscriptionError as exc:
        assert "25MB" in str(exc)
    finally:
        if os.path.exists(destination):
            os.unlink(destination)
        ws.httpx = httpx


# --- video frames (real ffmpeg, self-generated clip, zero cost) ---

def _make_clip(seconds: int) -> str:
    import imageio_ffmpeg

    path = tempfile.mktemp(suffix=".mp4")
    subprocess.run(
        [
            imageio_ffmpeg.get_ffmpeg_exe(), "-y",
            "-f", "lavfi", "-i", f"testsrc=size=640x360:rate=10:duration={seconds}",
            "-f", "lavfi", "-i", "anullsrc", "-shortest", "-pix_fmt", "yuv420p", path,
        ],
        capture_output=True,
        check=True,
    )
    return path


def test_duration_is_read_without_ffprobe():
    clip = _make_clip(6)
    try:
        assert abs(probe_duration(__import__("imageio_ffmpeg").get_ffmpeg_exe(), clip) - 6) < 0.5
    finally:
        os.unlink(clip)


def test_requested_number_of_frames_comes_back_for_a_short_clip():
    clip = _make_clip(6)
    try:
        frames = asyncio.run(extract_frames(clip, 3))
        assert len(frames) == 3
        assert all(base64.b64decode(f)[:2] == b"\xff\xd8" for f in frames)
    finally:
        os.unlink(clip)


def test_long_clip_still_yields_evenly_spread_frames():
    clip = _make_clip(90)
    try:
        assert len(asyncio.run(extract_frames(clip, 3))) == 3
    finally:
        os.unlink(clip)


def test_frame_extraction_can_be_disabled():
    assert asyncio.run(extract_frames("/nonexistent.mp4", 0)) == []


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failures = 0
    for test in tests:
        try:
            test()
            print(f"  PASS  {test.__name__}")
        except AssertionError as exc:
            failures += 1
            print(f"  FAIL  {test.__name__}: {exc}")
    print(f"\n{len(tests) - failures}/{len(tests)} passed")
    sys.exit(1 if failures else 0)
