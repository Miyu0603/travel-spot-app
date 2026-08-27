import json
import os
import tempfile

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.source import Source, SourceStatusEnum
from app.models.spot import Spot, Tag
from app.schemas.source import SourceCreate, SourceManualCreate, SourceResponse, ScrapeResult
from app.services.scraper import scrape_url, detect_platform
from app.services.ai_extractor import ExtractionError, extract_spots_from_text
from app.services.geo_service import enrich_spots
from app.services.media_service import fetch_images_as_data_urls, frames_to_data_urls
from app.services.rate_limit import enforce_extraction_limit
from app.services.video_service import FrameExtractionError, extract_frames
from app.services.whisper_service import (
    TranscriptionError,
    download_video,
    transcribe_file,
)

router = APIRouter()


@router.post(
    "/scrape",
    response_model=ScrapeResult,
    dependencies=[Depends(enforce_extraction_limit)],
)
async def scrape_and_extract(source_in: SourceCreate, db: Session = Depends(get_db)):
    """
    Main pipeline: 
    1. Scrape URL (Apify)
    2. Transcribe video if present (Whisper)
    3. Extract spots with AI (GPT)
    4. Enrich with geo data (Google Places)
    5. Save to database
    """
    platform = detect_platform(source_in.url)

    # Create source record
    source = Source(url=source_in.url, platform=platform, status=SourceStatusEnum.PROCESSING)
    db.add(source)
    db.commit()
    db.refresh(source)

    # Step 1: Scrape
    scrape_result = await scrape_url(source_in.url)

    if not scrape_result.get("success"):
        source.status = SourceStatusEnum.FAILED
        source.error_message = scrape_result.get("error", "Unknown error")
        db.commit()
        return ScrapeResult(
            source=_source_to_response(source),
            message=f"抓取失敗：{source.error_message}。請嘗試手動貼上內容。",
        )

    text = scrape_result.get("text", "")

    # Step 2: pull everything the post carries besides its caption — spoken
    # narration, on-screen text in the video, and text baked into images.
    text, frames, warnings = await _harvest_video(scrape_result.get("video_url"), text)
    image_urls = scrape_result.get("images") or []
    images, failed_images = await fetch_images_as_data_urls(
        image_urls, settings.max_post_images
    )
    if failed_images:
        warnings.append(
            f"貼文有 {len(image_urls)} 張圖片，其中 {failed_images} 張讀取失敗"
            "（圖片網址可能已失效）"
        )
    if image_urls and not images and settings.max_post_images > 0:
        warnings.append("圖片全數無法讀取，圖卡中的景點資訊本次未納入")

    source.raw_content = text
    db.commit()

    # Step 3 & 4: AI extraction + geo enrichment
    try:
        spots_data, discarded = await _process_text(text, source, db, images + frames)
    except ExtractionError as exc:
        return _extraction_failed(source, exc, db)

    source.status = SourceStatusEnum.COMPLETED
    db.commit()

    return ScrapeResult(
        source=_source_to_response(source),
        spots=spots_data,
        message=_success_message(len(spots_data), discarded, warnings),
    )


@router.post(
    "/manual",
    response_model=ScrapeResult,
    dependencies=[Depends(enforce_extraction_limit)],
)
async def manual_extract(source_in: SourceManualCreate, db: Session = Depends(get_db)):
    """
    Fallback: user manually pastes content.
    Runs AI extraction + geo enrichment on the pasted text.
    """
    source = Source(
        url=source_in.url,
        platform=source_in.platform,
        raw_content=source_in.raw_content,
        status=SourceStatusEnum.PROCESSING,
    )
    db.add(source)
    db.commit()
    db.refresh(source)

    try:
        spots_data, discarded = await _process_text(source_in.raw_content, source, db)
    except ExtractionError as exc:
        return _extraction_failed(source, exc, db)

    source.status = SourceStatusEnum.COMPLETED
    db.commit()

    return ScrapeResult(
        source=_source_to_response(source),
        spots=spots_data,
        message=_success_message(len(spots_data), discarded),
    )


@router.get("/", response_model=list[SourceResponse])
def list_sources(skip: int = 0, limit: int = 20, db: Session = Depends(get_db)):
    """List all source records."""
    sources = db.query(Source).order_by(Source.created_at.desc()).offset(skip).limit(limit).all()
    return [_source_to_response(s) for s in sources]


async def _harvest_video(video_url: str | None, text: str) -> tuple[str, list[str], list[str]]:
    """Transcribe a post's video and sample frames from it.

    The video is downloaded once and reused for both, and every failure here is
    reported rather than swallowed but never aborts the extraction — the caption
    alone may still hold the spots.
    """
    if not video_url:
        return text, [], []

    warnings: list[str] = []
    frames: list[str] = []

    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
        tmp_path = tmp.name
    try:
        try:
            await download_video(video_url, tmp_path)
        except TranscriptionError as exc:
            return text, [], [f"影片處理失敗：{exc}"]

        try:
            transcript = await transcribe_file(tmp_path)
            if transcript.strip():
                text = f"{text}\n\n[影片逐字稿]\n{transcript}"
        except TranscriptionError as exc:
            warnings.append(f"影片轉錄失敗：{exc}")

        try:
            frames = frames_to_data_urls(await extract_frames(tmp_path))
        except FrameExtractionError as exc:
            warnings.append(f"影片畫面擷取失敗：{exc}")
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)

    return text, frames, warnings


async def _process_text(
    text: str, source: Source, db: Session, images: list[str] | None = None
) -> tuple[list[dict], int]:
    """Extract spots from text using AI, enrich with geo, and save to DB.

    Returns (saved_spots, discarded_count). Propagates ExtractionError so the
    caller can report a real failure instead of an empty result.
    """
    raw_spots, discarded = await extract_spots_from_text(text, images)
    if not raw_spots:
        return [], discarded

    # Geo enrichment
    enriched_spots = await enrich_spots(raw_spots)

    # Save to database (skip duplicates by title + address)
    saved = []
    for spot_data in enriched_spots:
        title = spot_data.get("title", "")
        address = spot_data.get("address", "")

        existing = db.query(Spot).filter(
            Spot.title == title,
            Spot.address == address,
        ).first()
        if existing:
            continue

        spot = Spot(
            title=title,
            description=spot_data.get("description", ""),
            address=address,
            latitude=spot_data.get("latitude"),
            longitude=spot_data.get("longitude"),
            google_maps_url=spot_data.get("google_maps_url", ""),
            business_hours=spot_data.get("business_hours", ""),
            notes=spot_data.get("notes", ""),
            region=spot_data.get("region", "taiwan"),
            continent=spot_data.get("continent") or None,
            country=spot_data.get("country", ""),
            city=spot_data.get("city", ""),
            source_type="url",
            source_id=source.id,
        )
        db.add(spot)
        saved.append(spot_data)

    db.commit()
    return saved, discarded


def _extraction_failed(source: Source, exc: ExtractionError, db: Session) -> ScrapeResult:
    """Record the failure on the source so it is not left looking successful."""
    source.status = SourceStatusEnum.FAILED
    source.error_message = str(exc)
    db.commit()
    return ScrapeResult(
        source=_source_to_response(source),
        message=f"萃取失敗：{exc}",
    )


def _success_message(saved: int, discarded: int, warnings: list[str] | None = None) -> str:
    message = f"成功萃取 {saved} 個景點"
    if discarded:
        # Say so rather than silently returning fewer spots than the post held.
        message += f"（另有 {discarded} 筆資料格式有誤已略過）"
    if warnings:
        # Partial failures still change what was found; hiding them makes a
        # short result look like the post simply had less in it.
        message += "。" + "；".join(warnings)
    return message


def _source_to_response(source: Source) -> SourceResponse:
    return SourceResponse(
        id=source.id,
        url=source.url or "",
        platform=source.platform,
        status=source.status,
        raw_content=source.raw_content or "",
        error_message=source.error_message or "",
        created_at=source.created_at,
    )
