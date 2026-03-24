from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from typing import Optional
from sqlalchemy import func
from sqlalchemy.orm import Session
from typing import Optional

from app.dependencies import get_db, require_ranger
from app.models import Campaign, Pokemon, Ranger, Sighting
from app.schemas import (
    ConfirmationResponse,
    MessageResponse,
    PaginatedSightingsResponse,
    SightingCreate,
    SightingResponse,
)
from app.services.sighting_service import enrich_sighting

router = APIRouter(tags=["Sightings"])


@router.get("/sightings", response_model=PaginatedSightingsResponse)
def list_sightings(
    db: Session = Depends(get_db),
    pokemon_id: Optional[int] = Query(None, description="Filter by Pokémon species ID"),
    region: Optional[str] = Query(None, description="Filter by region name"),
    weather: Optional[str] = Query(None, description="Filter by weather condition"),
    time_of_day: Optional[str] = Query(None, description="Filter by time of day"),
    ranger_id: Optional[str] = Query(None, description="Filter by ranger UUID"),
    date_from: Optional[datetime] = Query(None, description="Start of date range (inclusive)"),
    date_to: Optional[datetime] = Query(None, description="End of date range (inclusive)"),
    limit: int = Query(20, ge=1, le=100, description="Page size"),
    offset: int = Query(0, ge=0, description="Number of records to skip"),
):
    """List sightings with optional filters and pagination."""
    query = (
        db.query(Sighting, Pokemon, Ranger)
        .join(Pokemon, Sighting.pokemon_id == Pokemon.id)
        .join(Ranger, Sighting.ranger_id == Ranger.id)
    )
    count_query = db.query(func.count(Sighting.id))

    if pokemon_id is not None:
        query = query.filter(Sighting.pokemon_id == pokemon_id)
        count_query = count_query.filter(Sighting.pokemon_id == pokemon_id)
    if region is not None:
        query = query.filter(Sighting.region == region)
        count_query = count_query.filter(Sighting.region == region)
    if weather is not None:
        query = query.filter(Sighting.weather == weather)
        count_query = count_query.filter(Sighting.weather == weather)
    if time_of_day is not None:
        query = query.filter(Sighting.time_of_day == time_of_day)
        count_query = count_query.filter(Sighting.time_of_day == time_of_day)
    if ranger_id is not None:
        query = query.filter(Sighting.ranger_id == ranger_id)
        count_query = count_query.filter(Sighting.ranger_id == ranger_id)
    if date_from is not None:
        query = query.filter(Sighting.date >= date_from)
        count_query = count_query.filter(Sighting.date >= date_from)
    if date_to is not None:
        query = query.filter(Sighting.date <= date_to)
        count_query = count_query.filter(Sighting.date <= date_to)

    total = count_query.scalar()
    rows = query.order_by(Sighting.date.desc()).offset(offset).limit(limit).all()
    items = [enrich_sighting(s, p, r) for s, p, r in rows]

    return PaginatedSightingsResponse(total=total, limit=limit, offset=offset, items=items)


@router.post("/sightings", response_model=SightingResponse, status_code=201)
def create_sighting(
    sighting: SightingCreate,
    db: Session = Depends(get_db),
    ranger: Ranger = Depends(require_ranger),
):
    pokemon = db.query(Pokemon).filter(Pokemon.id == sighting.pokemon_id).first()
    if not pokemon:
        raise HTTPException(status_code=404, detail="Pokémon not found")

    if sighting.campaign_id is not None:
        campaign = db.query(Campaign).filter(Campaign.id == sighting.campaign_id).first()
        if not campaign:
            raise HTTPException(status_code=404, detail="Campaign not found")
        if campaign.status != "active":
            raise HTTPException(
                status_code=400, detail="Sightings can only be added to active campaigns"
            )

    new_sighting = Sighting(
        pokemon_id=sighting.pokemon_id,
        ranger_id=ranger.id,
        region=sighting.region,
        route=sighting.route,
        date=sighting.date,
        weather=sighting.weather,
        time_of_day=sighting.time_of_day,
        height=sighting.height,
        weight=sighting.weight,
        is_shiny=sighting.is_shiny,
        notes=sighting.notes,
        latitude=sighting.latitude,
        longitude=sighting.longitude,
        campaign_id=sighting.campaign_id,
    )
    db.add(new_sighting)
    db.commit()
    db.refresh(new_sighting)
    return enrich_sighting(new_sighting, pokemon, ranger)


@router.get("/sightings/{sighting_id}", response_model=SightingResponse)
def get_sighting(sighting_id: str, db: Session = Depends(get_db)):
    row = (
        db.query(Sighting, Pokemon, Ranger)
        .join(Pokemon, Sighting.pokemon_id == Pokemon.id)
        .join(Ranger, Sighting.ranger_id == Ranger.id)
        .filter(Sighting.id == sighting_id)
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Sighting not found")
    sighting, pokemon, ranger = row
    return enrich_sighting(sighting, pokemon, ranger)


@router.delete("/sightings/{sighting_id}", response_model=MessageResponse)
def delete_sighting(
    sighting_id: str,
    db: Session = Depends(get_db),
    x_user_id: Optional[str] = Header(None),
):
    if not x_user_id:
        raise HTTPException(status_code=401, detail="X-User-ID header is required")

    sighting = db.query(Sighting).filter(Sighting.id == sighting_id).first()
    if not sighting:
        raise HTTPException(status_code=404, detail="Sighting not found")

    if sighting.ranger_id != x_user_id:
        raise HTTPException(status_code=403, detail="You can only delete your own sightings")

    if sighting.campaign_id:
        campaign = db.query(Campaign).filter(Campaign.id == sighting.campaign_id).first()
        if campaign and campaign.status in ("completed", "archived"):
            raise HTTPException(
                status_code=409, detail="Cannot delete sightings from a completed campaign"
            )

    db.delete(sighting)
    db.commit()
    return MessageResponse(detail="Sighting deleted")


@router.post("/sightings/{sighting_id}/confirm", response_model=SightingResponse)
def confirm_sighting(
    sighting_id: str,
    db: Session = Depends(get_db),
    ranger: Ranger = Depends(require_ranger),
):
    sighting = db.query(Sighting).filter(Sighting.id == sighting_id).first()
    if not sighting:
        raise HTTPException(status_code=404, detail="Sighting not found")

    if sighting.ranger_id == ranger.id:
        raise HTTPException(status_code=403, detail="You cannot confirm your own sighting")

    if sighting.is_confirmed:
        raise HTTPException(status_code=409, detail="Sighting has already been confirmed")

    sighting.confirmed_by = ranger.id
    sighting.confirmed_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db.commit()
    db.refresh(sighting)

    pokemon = db.query(Pokemon).filter(Pokemon.id == sighting.pokemon_id).first()
    reporter = db.query(Ranger).filter(Ranger.id == sighting.ranger_id).first()
    return enrich_sighting(sighting, pokemon, reporter)


@router.get("/sightings/{sighting_id}/confirmation", response_model=ConfirmationResponse)
def get_confirmation(sighting_id: str, db: Session = Depends(get_db)):
    sighting = db.query(Sighting).filter(Sighting.id == sighting_id).first()
    if not sighting:
        raise HTTPException(status_code=404, detail="Sighting not found")
    if not sighting.is_confirmed:
        raise HTTPException(status_code=404, detail="Sighting has not been confirmed")

    return ConfirmationResponse(
        sighting_id=sighting_id,
        confirmed_by=sighting.confirmed_by,
        confirmed_at=sighting.confirmed_at,
    )
