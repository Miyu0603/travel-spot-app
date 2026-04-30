import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.source import Source, SourceStatusEnum
from app.models.spot import Spot, Tag
from app.schemas.source import SourceCreate, SourceManualCreate, SourceResponse, ScrapeResult
from app.services.scraper import scrape_url, detect_platform
from app.services.ai_extractor import extract_spots_from_text
from app.services.geo_service import enrich_spots
from app.services.whisper_service import transcribe_video

router = APIRouter()


@router.post("/scrape", response_model=ScrapeResult)
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

    # Step 2: If there's a video, transcribe it
    video_url = scrape_result.get("video_url")
    if video_url:
        transcript = await transcribe_video(video_url)
        if transcript:
            text = f"{text}\n\n[影片逐字稿]\n{transcript}"

    source.raw_content = text
    db.commit()

    # Step 3 & 4: AI extraction + geo enrichment
    spots_data = await _process_text(text, source, db)

    source.status = SourceStatusEnum.COMPLETED
    db.commit()

    return ScrapeResult(
        source=_source_to_response(source),
        spots=spots_data,
        message=f"成功萃取 {len(spots_data)} 個景點",
    )


@router.post("/manual", response_model=ScrapeResult)
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

    spots_data = await _process_text(source_in.raw_content, source, db)

    source.status = SourceStatusEnum.COMPLETED
    db.commit()

    return ScrapeResult(
        source=_source_to_response(source),
        spots=spots_data,
        message=f"成功萃取 {len(spots_data)} 個景點",
    )


@router.get("/", response_model=list[SourceResponse])
def list_sources(skip: int = 0, limit: int = 20, db: Session = Depends(get_db)):
    """List all source records."""
    sources = db.query(Source).order_by(Source.created_at.desc()).offset(skip).limit(limit).all()
    return [_source_to_response(s) for s in sources]


async def _process_text(text: str, source: Source, db: Session) -> list[dict]:
    """Extract spots from text using AI, enrich with geo, and save to DB."""
    # AI extraction
    raw_spots = await extract_spots_from_text(text)
    if not raw_spots:
        return []

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
    return saved


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
