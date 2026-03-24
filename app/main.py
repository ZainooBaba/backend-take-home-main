import math
from collections import defaultdict

from fastapi import FastAPI, HTTPException, Header, Query, Depends
from sqlalchemy.orm import Session
from sqlalchemy import Integer, func
from typing import Optional, Any
from datetime import datetime

from app.database import engine, SessionLocal, Base
from app.models import Campaign, Pokemon, Trainer, Ranger, Sighting
from app.schemas import (
    CampaignCreate,
    CampaignResponse,
    CampaignSummaryResponse,
    CampaignTransition,
    CampaignUpdate,
    Anomaly,
    ConfirmationResponse,
    RarityAnalysisResponse,
    RegionalSummaryResponse,
    SpeciesCount,
    TierBreakdown,
    TopEntry,
    TrainerCreate,
    TrainerResponse,
    RangerCreate,
    RangerResponse,
    PokemonResponse,
    PokemonSearchResult,
    SightingCreate,
    SightingResponse,
    UserLookupResponse,
    MessageResponse,
    PaginatedSightingsResponse,
)

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Endeavor PokéTracker", version="0.1.0")


# ---------- helpers ----------

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


VALID_TRANSITIONS = {"draft": "active", "active": "completed", "completed": "archived"}

# Rarity tier ordering (highest → lowest) used for analysis
TIER_ORDER = ["mythical", "legendary", "rare", "uncommon", "common"]


def _rarity_tier(is_mythical: bool, is_legendary: bool, capture_rate: int) -> str:
    if is_mythical:
        return "mythical"
    if is_legendary:
        return "legendary"
    if capture_rate < 75:
        return "rare"
    if capture_rate < 150:
        return "uncommon"
    return "common"

REGION_TO_GENERATION = {
    "kanto": 1,
    "johto": 2,
    "hoenn": 3,
    "sinnoh": 4,
}


def _enrich_sighting(sighting: Sighting, pokemon: Pokemon, ranger: Ranger) -> SightingResponse:
    """Build a SightingResponse from ORM objects without extra queries."""
    resp = SightingResponse.model_validate(sighting)
    resp.pokemon_name = pokemon.name if pokemon else None
    resp.ranger_name = ranger.name if ranger else None
    return resp


# ---------- Trainers ----------

@app.post("/trainers")
def create_trainer(trainer: TrainerCreate, db: Session = Depends(get_db)) -> Trainer:
    new_trainer = Trainer(name=trainer.name, email=trainer.email)
    db.add(new_trainer)
    db.commit()
    db.refresh(new_trainer)
    return new_trainer


@app.get("/trainers/{trainer_id}", response_model=TrainerResponse)
def get_trainer(trainer_id: str, db: Session = Depends(get_db)):
    trainer = db.query(Trainer).filter(Trainer.id == trainer_id).first()
    if not trainer:
        raise HTTPException(status_code=404, detail="Trainer not found")
    return trainer


# ---------- Rangers ----------

@app.post("/rangers", response_model=RangerResponse)
def create_ranger(ranger: RangerCreate, db: Session = Depends(get_db)):
    new_ranger = Ranger(
        name=ranger.name,
        email=ranger.email,
        specialization=ranger.specialization,
    )
    db.add(new_ranger)
    db.commit()
    db.refresh(new_ranger)
    return new_ranger


@app.get("/rangers/{ranger_id}", response_model=RangerResponse)
def get_ranger(ranger_id: str, db: Session = Depends(get_db)):
    ranger = db.query(Ranger).filter(Ranger.id == ranger_id).first()
    if not ranger:
        raise HTTPException(status_code=404, detail="Ranger not found")
    return ranger


@app.get("/rangers/{ranger_id}/sightings", response_model=list[SightingResponse])
def get_ranger_sightings(ranger_id: str, db: Session = Depends(get_db)):
    ranger = db.query(Ranger).filter(Ranger.id == ranger_id).first()
    if not ranger:
        raise HTTPException(status_code=404, detail="Ranger not found")

    # Use a JOIN instead of N+1 queries
    rows = (
        db.query(Sighting, Pokemon)
        .join(Pokemon, Sighting.pokemon_id == Pokemon.id)
        .filter(Sighting.ranger_id == ranger_id)
        .all()
    )
    return [_enrich_sighting(s, p, ranger) for s, p in rows]


# ---------- User Lookup ----------

@app.get("/users/lookup", response_model=UserLookupResponse)
def lookup_user(name: str = Query(...), db: Session = Depends(get_db)):
    trainer = db.query(Trainer).filter(Trainer.name == name).first()
    if trainer:
        return UserLookupResponse(id=trainer.id, name=trainer.name, role="trainer")
    ranger = db.query(Ranger).filter(Ranger.name == name).first()
    if ranger:
        return UserLookupResponse(id=ranger.id, name=ranger.name, role="ranger")
    raise HTTPException(status_code=404, detail="User not found")


# ---------- Pokédex ----------

@app.get("/pokedex", response_model=list[PokemonResponse])
def list_pokemon(db: Session = Depends(get_db)):
    pokemon_list = db.query(Pokemon).all()
    return pokemon_list


@app.get("/pokedex/search", response_model=list[PokemonSearchResult])
def search_pokemon(name: str = Query(..., min_length=1), db: Session = Depends(get_db)):
    return db.query(Pokemon).filter(Pokemon.name.ilike(f"{name}%")).all()


@app.get("/pokedex/{pokemon_id_or_region}")
def get_pokemon(pokemon_id_or_region: str, db: Session = Depends(get_db)):
    # Check if it's a numeric ID
    try:
        pokemon_id = int(pokemon_id_or_region)
        pokemon = db.query(Pokemon).filter(Pokemon.id == pokemon_id).first()
        if not pokemon:
            raise HTTPException(status_code=404, detail="Pokémon not found")
        return PokemonResponse.model_validate(pokemon)
    except ValueError:
        pass

    # Check if it's a region name or generation number
    region_lower = pokemon_id_or_region.lower()
    generation = REGION_TO_GENERATION.get(region_lower)
    if generation is None:
        try:
            generation = int(pokemon_id_or_region)
        except ValueError:
            raise HTTPException(status_code=404, detail="Invalid Pokémon ID or region name")

    pokemon_list = db.query(Pokemon).filter(Pokemon.generation == generation).all()
    return [PokemonResponse.model_validate(p) for p in pokemon_list]


# ---------- Campaigns ----------

@app.post("/campaigns", response_model=CampaignResponse)
def create_campaign(
    campaign: CampaignCreate,
    db: Session = Depends(get_db),
    x_user_id: Optional[str] = Header(None),
):
    if not x_user_id:
        raise HTTPException(status_code=401, detail="X-User-ID header is required")
    ranger = db.query(Ranger).filter(Ranger.id == x_user_id).first()
    if not ranger:
        raise HTTPException(status_code=403, detail="Only rangers can create campaigns")

    new_campaign = Campaign(
        name=campaign.name,
        description=campaign.description,
        region=campaign.region,
        start_date=campaign.start_date,
        end_date=campaign.end_date,
        created_by=x_user_id,
    )
    db.add(new_campaign)
    db.commit()
    db.refresh(new_campaign)
    return new_campaign


@app.get("/campaigns/{campaign_id}", response_model=CampaignResponse)
def get_campaign(campaign_id: str, db: Session = Depends(get_db)):
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return campaign


@app.patch("/campaigns/{campaign_id}", response_model=CampaignResponse)
def update_campaign(
    campaign_id: str,
    updates: CampaignUpdate,
    db: Session = Depends(get_db),
    x_user_id: Optional[str] = Header(None),
):
    if not x_user_id:
        raise HTTPException(status_code=401, detail="X-User-ID header is required")
    ranger = db.query(Ranger).filter(Ranger.id == x_user_id).first()
    if not ranger:
        raise HTTPException(status_code=403, detail="Only rangers can update campaigns")

    campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    for field, value in updates.model_dump(exclude_none=True).items():
        setattr(campaign, field, value)

    db.commit()
    db.refresh(campaign)
    return campaign


@app.post("/campaigns/{campaign_id}/transition", response_model=CampaignResponse)
def transition_campaign(
    campaign_id: str,
    body: CampaignTransition,
    db: Session = Depends(get_db),
    x_user_id: Optional[str] = Header(None),
):
    if not x_user_id:
        raise HTTPException(status_code=401, detail="X-User-ID header is required")
    ranger = db.query(Ranger).filter(Ranger.id == x_user_id).first()
    if not ranger:
        raise HTTPException(status_code=403, detail="Only rangers can transition campaigns")

    campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    if VALID_TRANSITIONS.get(campaign.status) != body.status:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot transition from '{campaign.status}' to '{body.status}'",
        )

    campaign.status = body.status
    db.commit()
    db.refresh(campaign)
    return campaign


@app.get("/campaigns/{campaign_id}/summary", response_model=CampaignSummaryResponse)
def get_campaign_summary(campaign_id: str, db: Session = Depends(get_db)):
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    row = db.query(
        func.count(Sighting.id),
        func.count(Sighting.pokemon_id.distinct()),
        func.count(Sighting.ranger_id.distinct()),
        func.min(Sighting.date),
        func.max(Sighting.date),
    ).filter(Sighting.campaign_id == campaign_id).one()

    total, unique_species, contributing_rangers, earliest, latest = row
    return CampaignSummaryResponse(
        campaign_id=campaign_id,
        total_sightings=total,
        unique_species=unique_species,
        contributing_rangers=contributing_rangers,
        earliest_sighting=earliest,
        latest_sighting=latest,
    )


# ---------- Sightings ----------

@app.get("/sightings", response_model=PaginatedSightingsResponse)
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
    """
    List sightings with optional filters and pagination.
    Returns total matching count alongside the page of results.
    """
    # Base query with JOINs to avoid N+1
    query = (
        db.query(Sighting, Pokemon, Ranger)
        .join(Pokemon, Sighting.pokemon_id == Pokemon.id)
        .join(Ranger, Sighting.ranger_id == Ranger.id)
    )

    # Also build a count query on Sighting only (faster than counting joined rows)
    count_query = db.query(func.count(Sighting.id))

    # Apply filters to both queries
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

    rows = (
        query
        .order_by(Sighting.date.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    items = [_enrich_sighting(s, p, r) for s, p, r in rows]

    return PaginatedSightingsResponse(
        total=total,
        limit=limit,
        offset=offset,
        items=items,
    )


@app.post("/sightings", response_model=SightingResponse)
def create_sighting(
    sighting: SightingCreate,
    db: Session = Depends(get_db),
    x_user_id: Optional[str] = Header(None),
):
    if not x_user_id:
        raise HTTPException(status_code=401, detail="X-User-ID header is required")

    # Check that user is a ranger
    ranger = db.query(Ranger).filter(Ranger.id == x_user_id).first()
    if not ranger:
        raise HTTPException(status_code=403, detail="Only rangers can log sightings")

    # Check pokemon exists
    pokemon = db.query(Pokemon).filter(Pokemon.id == sighting.pokemon_id).first()
    if not pokemon:
        raise HTTPException(status_code=404, detail="Pokémon not found")

    # Validate campaign if provided
    if sighting.campaign_id is not None:
        campaign = db.query(Campaign).filter(Campaign.id == sighting.campaign_id).first()
        if not campaign:
            raise HTTPException(status_code=404, detail="Campaign not found")
        if campaign.status != "active":
            raise HTTPException(status_code=400, detail="Sightings can only be added to active campaigns")

    new_sighting = Sighting(
        pokemon_id=sighting.pokemon_id,
        ranger_id=x_user_id,
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

    return _enrich_sighting(new_sighting, pokemon, ranger)


@app.get("/sightings/{sighting_id}", response_model=SightingResponse)
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
    return _enrich_sighting(sighting, pokemon, ranger)


@app.delete("/sightings/{sighting_id}", response_model=MessageResponse)
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
            raise HTTPException(status_code=403, detail="Cannot delete sightings from a completed campaign")

    db.delete(sighting)
    db.commit()
    return MessageResponse(detail="Sighting deleted")


# ---------- Regions ----------

@app.get("/regions/{region_name}/summary", response_model=RegionalSummaryResponse)
def get_regional_summary(region_name: str, db: Session = Depends(get_db)):
    # Totals in a single pass
    totals = db.query(
        func.count(Sighting.id),
        func.sum(Sighting.is_confirmed.cast(Integer)),
        func.count(Sighting.pokemon_id.distinct()),
    ).filter(Sighting.region == region_name).one()

    total_sightings, confirmed_count, unique_species = totals
    total_sightings = total_sightings or 0
    confirmed_count = confirmed_count or 0
    unique_species = unique_species or 0

    # Top 5 Pokémon by sighting count
    top_poke_rows = (
        db.query(Pokemon.id, Pokemon.name, func.count(Sighting.id).label("cnt"))
        .join(Sighting, Sighting.pokemon_id == Pokemon.id)
        .filter(Sighting.region == region_name)
        .group_by(Pokemon.id, Pokemon.name)
        .order_by(func.count(Sighting.id).desc())
        .limit(5)
        .all()
    )
    top_pokemon = [TopEntry(id=r.id, name=r.name, count=r.cnt) for r in top_poke_rows]

    # Top 5 rangers by sighting count
    top_ranger_rows = (
        db.query(Ranger.id, Ranger.name, func.count(Sighting.id).label("cnt"))
        .join(Sighting, Sighting.ranger_id == Ranger.id)
        .filter(Sighting.region == region_name)
        .group_by(Ranger.id, Ranger.name)
        .order_by(func.count(Sighting.id).desc())
        .limit(5)
        .all()
    )
    top_rangers = [TopEntry(id=r.id, name=r.name, count=r.cnt) for r in top_ranger_rows]

    # Weather breakdown
    weather_rows = (
        db.query(Sighting.weather, func.count(Sighting.id))
        .filter(Sighting.region == region_name)
        .group_by(Sighting.weather)
        .all()
    )
    by_weather = {w: c for w, c in weather_rows}

    # Time-of-day breakdown
    tod_rows = (
        db.query(Sighting.time_of_day, func.count(Sighting.id))
        .filter(Sighting.region == region_name)
        .group_by(Sighting.time_of_day)
        .all()
    )
    by_time_of_day = {t: c for t, c in tod_rows}

    return RegionalSummaryResponse(
        region=region_name,
        total_sightings=total_sightings,
        confirmed_sightings=confirmed_count,
        unconfirmed_sightings=total_sightings - confirmed_count,
        unique_species=unique_species,
        top_pokemon=top_pokemon,
        top_rangers=top_rangers,
        by_weather=by_weather,
        by_time_of_day=by_time_of_day,
    )


@app.get("/regions/{region_name}/analysis", response_model=RarityAnalysisResponse)
def get_regional_analysis(region_name: str, db: Session = Depends(get_db)):
    """
    Rarity & encounter rate analysis for a region.

    A single JOIN query retrieves all (pokemon, sighting_count) pairs for the
    region. Python then buckets by rarity tier and runs a z-score anomaly
    check within each tier (see NOTES.md for reasoning).
    """
    rows = (
        db.query(
            Pokemon.id,
            Pokemon.name,
            Pokemon.capture_rate,
            Pokemon.is_legendary,
            Pokemon.is_mythical,
            func.count(Sighting.id).label("cnt"),
        )
        .join(Sighting, Sighting.pokemon_id == Pokemon.id)
        .filter(Sighting.region == region_name)
        .group_by(Pokemon.id)
        .all()
    )

    total_sightings = sum(r.cnt for r in rows)

    # Bucket species into tiers
    tier_species: dict[str, list[SpeciesCount]] = defaultdict(list)
    for r in rows:
        tier = _rarity_tier(r.is_mythical, r.is_legendary, r.capture_rate)
        tier_species[tier].append(SpeciesCount(pokemon_id=r.id, name=r.name, count=r.cnt))

    # Build ordered tier breakdown
    tiers: list[TierBreakdown] = []
    for tier_name in TIER_ORDER:
        species_list = tier_species.get(tier_name)
        if not species_list:
            continue
        tier_count = sum(s.count for s in species_list)
        percentage = round(100.0 * tier_count / total_sightings, 2) if total_sightings else 0.0
        tiers.append(TierBreakdown(
            tier=tier_name,
            count=tier_count,
            percentage=percentage,
            species=sorted(species_list, key=lambda s: -s.count),
        ))

    # Anomaly detection: z-score within tier (see NOTES.md)
    anomalies: list[Anomaly] = []
    for tier in tiers:
        if len(tier.species) < 2:
            continue
        counts = [s.count for s in tier.species]
        mean = sum(counts) / len(counts)
        variance = sum((c - mean) ** 2 for c in counts) / len(counts)
        stdev = math.sqrt(variance)
        if stdev == 0:
            continue
        for s in tier.species:
            z = (s.count - mean) / stdev
            if abs(z) >= 2.0:
                anomalies.append(Anomaly(
                    pokemon_id=s.pokemon_id,
                    name=s.name,
                    tier=tier.tier,
                    count=s.count,
                    tier_mean=round(mean, 2),
                    z_score=round(z, 2),
                    reason="over-represented" if z > 0 else "under-represented",
                ))

    return RarityAnalysisResponse(
        region=region_name,
        total_sightings=total_sightings,
        tiers=tiers,
        anomalies=anomalies,
    )


@app.post("/sightings/{sighting_id}/confirm", response_model=SightingResponse)
def confirm_sighting(
    sighting_id: str,
    db: Session = Depends(get_db),
    x_user_id: Optional[str] = Header(None),
):
    if not x_user_id:
        raise HTTPException(status_code=401, detail="X-User-ID header is required")

    ranger = db.query(Ranger).filter(Ranger.id == x_user_id).first()
    if not ranger:
        raise HTTPException(status_code=403, detail="Only rangers can confirm sightings")

    sighting = db.query(Sighting).filter(Sighting.id == sighting_id).first()
    if not sighting:
        raise HTTPException(status_code=404, detail="Sighting not found")

    if sighting.ranger_id == x_user_id:
        raise HTTPException(status_code=403, detail="You cannot confirm your own sighting")

    if sighting.is_confirmed:
        raise HTTPException(status_code=409, detail="Sighting has already been confirmed")

    sighting.is_confirmed = True
    sighting.confirmed_by = x_user_id
    sighting.confirmed_at = datetime.utcnow()
    db.commit()
    db.refresh(sighting)

    pokemon = db.query(Pokemon).filter(Pokemon.id == sighting.pokemon_id).first()
    reporter = db.query(Ranger).filter(Ranger.id == sighting.ranger_id).first()
    return _enrich_sighting(sighting, pokemon, reporter)


@app.get("/sightings/{sighting_id}/confirmation", response_model=ConfirmationResponse)
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