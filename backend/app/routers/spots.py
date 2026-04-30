from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.spot import Spot, Tag, RegionEnum, ContinentEnum
from app.schemas.spot import SpotCreate, SpotUpdate, SpotResponse

router = APIRouter()


@router.get("/", response_model=list[SpotResponse])
def list_spots(
    region: RegionEnum | None = None,
    continent: ContinentEnum | None = None,
    country: str | None = None,
    tag: str | None = None,
    search: str | None = None,
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
):
    """List spots with optional filters."""
    query = db.query(Spot)

    if region:
        query = query.filter(Spot.region == region)
    if continent:
        query = query.filter(Spot.continent == continent)
    if country:
        query = query.filter(Spot.country.ilike(f"%{country}%"))
    if tag:
        query = query.join(Spot.tags).filter(Tag.name == tag)
    if search:
        query = query.filter(
            Spot.title.ilike(f"%{search}%") | Spot.description.ilike(f"%{search}%")
        )

    spots = query.offset(skip).limit(limit).all()

    return [_spot_to_response(s) for s in spots]


@router.get("/{spot_id}", response_model=SpotResponse)
def get_spot(spot_id: int, db: Session = Depends(get_db)):
    """Get a single spot by ID."""
    spot = db.query(Spot).filter(Spot.id == spot_id).first()
    if not spot:
        raise HTTPException(status_code=404, detail="Spot not found")
    return _spot_to_response(spot)


@router.post("/", response_model=SpotResponse, status_code=201)
def create_spot(spot_in: SpotCreate, db: Session = Depends(get_db)):
    """Manually create a spot."""
    spot = Spot(
        title=spot_in.title,
        description=spot_in.description,
        address=spot_in.address,
        latitude=spot_in.latitude,
        longitude=spot_in.longitude,
        google_maps_url=spot_in.google_maps_url,
        business_hours=spot_in.business_hours,
        notes=spot_in.notes,
        region=spot_in.region,
        continent=spot_in.continent,
        country=spot_in.country,
        source_type=spot_in.source_type,
        images=spot_in.images,
    )

    # Handle tags
    for tag_name in spot_in.tags:
        tag = db.query(Tag).filter(Tag.name == tag_name).first()
        if not tag:
            tag = Tag(name=tag_name)
            db.add(tag)
        spot.tags.append(tag)

    db.add(spot)
    db.commit()
    db.refresh(spot)
    return _spot_to_response(spot)


@router.put("/{spot_id}", response_model=SpotResponse)
def update_spot(spot_id: int, spot_in: SpotUpdate, db: Session = Depends(get_db)):
    """Update a spot."""
    spot = db.query(Spot).filter(Spot.id == spot_id).first()
    if not spot:
        raise HTTPException(status_code=404, detail="Spot not found")

    update_data = spot_in.model_dump(exclude_unset=True)
    tags = update_data.pop("tags", None)

    for field, value in update_data.items():
        setattr(spot, field, value)

    if tags is not None:
        spot.tags.clear()
        for tag_name in tags:
            tag = db.query(Tag).filter(Tag.name == tag_name).first()
            if not tag:
                tag = Tag(name=tag_name)
                db.add(tag)
            spot.tags.append(tag)

    db.commit()
    db.refresh(spot)
    return _spot_to_response(spot)


@router.delete("/{spot_id}", status_code=204)
def delete_spot(spot_id: int, db: Session = Depends(get_db)):
    """Delete a spot."""
    spot = db.query(Spot).filter(Spot.id == spot_id).first()
    if not spot:
        raise HTTPException(status_code=404, detail="Spot not found")
    db.delete(spot)
    db.commit()


def _spot_to_response(spot: Spot) -> SpotResponse:
    return SpotResponse(
        id=spot.id,
        title=spot.title,
        description=spot.description or "",
        address=spot.address or "",
        latitude=spot.latitude,
        longitude=spot.longitude,
        google_maps_url=spot.google_maps_url or "",
        business_hours=spot.business_hours or "",
        notes=spot.notes or "",
        region=spot.region,
        continent=spot.continent,
        country=spot.country or "",
        city=spot.city or "",
        source_type=spot.source_type or "manual",
        source_id=spot.source_id,
        images=spot.images or "[]",
        tags=[t.name for t in spot.tags],
        created_at=spot.created_at,
        updated_at=spot.updated_at,
    )
