from fastapi import FastAPI, HTTPException, Header, Query, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Optional, Any
from datetime import datetime

from app.database import engine, SessionLocal, Base
from app.models import Pokemon, Trainer, Ranger, Sighting
from app.schemas import (
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

    db.delete(sighting)
    db.commit()
    return MessageResponse(detail="Sighting deleted")