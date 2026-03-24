from fastapi import FastAPI, HTTPException, Header, Query, Depends
from sqlalchemy.orm import Session
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
)

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Endeavor PokéTracker", version="0.0.1")


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
    sightings = db.query(Sighting).filter(Sighting.ranger_id == ranger_id).all()
    result = []
    for s in sightings:
        pokemon = db.query(Pokemon).filter(Pokemon.id == s.pokemon_id).first()
        resp = SightingResponse.model_validate(s)
        resp.pokemon_name = pokemon.name if pokemon else None
        resp.ranger_name = ranger.name
        result.append(resp)
    return result


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

    resp = SightingResponse.model_validate(new_sighting)
    resp.pokemon_name = pokemon.name
    resp.ranger_name = ranger.name
    return resp


@app.get("/sightings/{sighting_id}", response_model=SightingResponse)
def get_sighting(sighting_id: str, db: Session = Depends(get_db)):
    sighting = db.query(Sighting).filter(Sighting.id == sighting_id).first()
    if not sighting:
        raise HTTPException(status_code=404, detail="Sighting not found")

    pokemon = db.query(Pokemon).filter(Pokemon.id == sighting.pokemon_id).first()
    ranger = db.query(Ranger).filter(Ranger.id == sighting.ranger_id).first()

    resp = SightingResponse.model_validate(sighting)
    resp.pokemon_name = pokemon.name if pokemon else None
    resp.ranger_name = ranger.name if ranger else None
    return resp


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
