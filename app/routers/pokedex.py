from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session
from typing import Optional

from app.dependencies import get_db
from app.models import Pokemon, Trainer, TrainerCatch
from app.schemas import PaginatedPokedexResponse, PokemonResponse, PokemonSearchResult

router = APIRouter(tags=["Pokédex"])

REGION_TO_GENERATION = {
    "kanto": 1,
    "johto": 2,
    "hoenn": 3,
    "sinnoh": 4,
}


@router.get("/pokedex", response_model=PaginatedPokedexResponse)
def list_pokemon(
    db: Session = Depends(get_db),
    limit: int = Query(20, ge=1, le=100, description="Page size"),
    offset: int = Query(0, ge=0, description="Number of records to skip"),
):
    total = db.query(func.count(Pokemon.id)).scalar()
    items = db.query(Pokemon).order_by(Pokemon.id).offset(offset).limit(limit).all()
    return PaginatedPokedexResponse(total=total, limit=limit, offset=offset, items=items)


@router.get("/pokedex/search", response_model=list[PokemonSearchResult])
def search_pokemon(name: str = Query(..., min_length=1), db: Session = Depends(get_db)):
    return db.query(Pokemon).filter(Pokemon.name.ilike(f"{name}%")).all()


@router.get("/pokedex/{pokemon_id}", response_model=PokemonResponse)
def get_pokemon_by_id(
    pokemon_id: int,
    db: Session = Depends(get_db),
    x_user_id: Optional[str] = Header(None),
):
    """Fetch a single Pokémon by numeric ID. Includes is_caught when called by a trainer."""
    pokemon = db.query(Pokemon).filter(Pokemon.id == pokemon_id).first()
    if not pokemon:
        raise HTTPException(status_code=404, detail="Pokémon not found")
    resp = PokemonResponse.model_validate(pokemon)
    if x_user_id:
        is_trainer = db.query(Trainer).filter(Trainer.id == x_user_id).first() is not None
        if is_trainer:
            caught = db.query(TrainerCatch).filter(
                TrainerCatch.trainer_id == x_user_id,
                TrainerCatch.pokemon_id == pokemon_id,
            ).first()
            resp.is_caught = caught is not None
    return resp


@router.get("/pokedex/region/{region_name}", response_model=list[PokemonResponse])
def get_pokemon_by_region(region_name: str, db: Session = Depends(get_db)):
    """List all Pokémon native to a region (by name or generation number)."""
    region_lower = region_name.lower()
    generation = REGION_TO_GENERATION.get(region_lower)
    if generation is None:
        try:
            generation = int(region_name)
        except ValueError:
            raise HTTPException(
                status_code=404,
                detail=f"Unknown region '{region_name}'. Valid names: {', '.join(REGION_TO_GENERATION)}",
            )
    return [PokemonResponse.model_validate(p) for p in
            db.query(Pokemon).filter(Pokemon.generation == generation).all()]
