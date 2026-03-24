from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session
from typing import Optional

from app.dependencies import get_db
from app.models import Pokemon, Trainer, TrainerCatch
from app.schemas import (
    CatchLogEntry,
    CatchSummaryResponse,
    MessageResponse,
    TrainerCreate,
    TrainerResponse,
)

router = APIRouter(tags=["Trainers"])


def _require_trainer_owner(trainer_id: str, x_user_id: Optional[str], db: Session) -> Trainer:
    """Validate that x_user_id is the trainer who owns this log. Returns the Trainer."""
    if not x_user_id:
        raise HTTPException(status_code=401, detail="X-User-ID header is required")
    trainer = db.query(Trainer).filter(Trainer.id == trainer_id).first()
    if not trainer:
        raise HTTPException(status_code=404, detail="Trainer not found")
    if x_user_id != trainer_id:
        raise HTTPException(status_code=403, detail="You can only modify your own Pokédex")
    return trainer


@router.post("/trainers", response_model=TrainerResponse, status_code=201)
def create_trainer(trainer: TrainerCreate, db: Session = Depends(get_db)):
    new_trainer = Trainer(name=trainer.name, email=trainer.email)
    db.add(new_trainer)
    db.commit()
    db.refresh(new_trainer)
    return new_trainer


@router.get("/trainers/{trainer_id}", response_model=TrainerResponse)
def get_trainer(trainer_id: str, db: Session = Depends(get_db)):
    trainer = db.query(Trainer).filter(Trainer.id == trainer_id).first()
    if not trainer:
        raise HTTPException(status_code=404, detail="Trainer not found")
    return trainer


# ---------- Catch Tracking ----------

@router.post(
    "/trainers/{trainer_id}/pokedex/{pokemon_id}",
    response_model=CatchLogEntry,
    status_code=201,
)
def mark_caught(
    trainer_id: str,
    pokemon_id: int,
    db: Session = Depends(get_db),
    x_user_id: Optional[str] = Header(None),
):
    _require_trainer_owner(trainer_id, x_user_id, db)

    pokemon = db.query(Pokemon).filter(Pokemon.id == pokemon_id).first()
    if not pokemon:
        raise HTTPException(status_code=404, detail="Pokémon not found")

    existing = db.query(TrainerCatch).filter(
        TrainerCatch.trainer_id == trainer_id,
        TrainerCatch.pokemon_id == pokemon_id,
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="Pokémon already marked as caught")

    catch = TrainerCatch(trainer_id=trainer_id, pokemon_id=pokemon_id)
    db.add(catch)
    db.commit()
    db.refresh(catch)
    return CatchLogEntry(pokemon_id=catch.pokemon_id, name=pokemon.name, caught_at=catch.caught_at)


@router.delete("/trainers/{trainer_id}/pokedex/{pokemon_id}", response_model=MessageResponse)
def unmark_caught(
    trainer_id: str,
    pokemon_id: int,
    db: Session = Depends(get_db),
    x_user_id: Optional[str] = Header(None),
):
    _require_trainer_owner(trainer_id, x_user_id, db)

    catch = db.query(TrainerCatch).filter(
        TrainerCatch.trainer_id == trainer_id,
        TrainerCatch.pokemon_id == pokemon_id,
    ).first()
    if not catch:
        raise HTTPException(status_code=404, detail="Pokémon not in catch log")

    db.delete(catch)
    db.commit()
    return MessageResponse(detail="Pokémon removed from catch log")


@router.get("/trainers/{trainer_id}/pokedex/summary", response_model=CatchSummaryResponse)
def get_catch_summary(trainer_id: str, db: Session = Depends(get_db)):
    trainer = db.query(Trainer).filter(Trainer.id == trainer_id).first()
    if not trainer:
        raise HTTPException(status_code=404, detail="Trainer not found")

    total_pokemon = db.query(func.count(Pokemon.id)).scalar() or 0
    total_caught = (
        db.query(func.count(TrainerCatch.pokemon_id))
        .filter(TrainerCatch.trainer_id == trainer_id)
        .scalar()
    ) or 0

    type_rows = (
        db.query(Pokemon.type1, func.count(TrainerCatch.pokemon_id).label("cnt"))
        .join(TrainerCatch, TrainerCatch.pokemon_id == Pokemon.id)
        .filter(TrainerCatch.trainer_id == trainer_id)
        .group_by(Pokemon.type1)
        .all()
    )
    gen_rows = (
        db.query(Pokemon.generation, func.count(TrainerCatch.pokemon_id).label("cnt"))
        .join(TrainerCatch, TrainerCatch.pokemon_id == Pokemon.id)
        .filter(TrainerCatch.trainer_id == trainer_id)
        .group_by(Pokemon.generation)
        .all()
    )

    completion_percentage = round(100.0 * total_caught / total_pokemon, 2) if total_pokemon else 0.0

    return CatchSummaryResponse(
        total_caught=total_caught,
        total_pokemon=total_pokemon,
        completion_percentage=completion_percentage,
        by_type={row.type1: row.cnt for row in type_rows},
        by_generation={str(row.generation): row.cnt for row in gen_rows},
    )


@router.get("/trainers/{trainer_id}/pokedex", response_model=list[CatchLogEntry])
def get_catch_log(trainer_id: str, db: Session = Depends(get_db)):
    trainer = db.query(Trainer).filter(Trainer.id == trainer_id).first()
    if not trainer:
        raise HTTPException(status_code=404, detail="Trainer not found")

    rows = (
        db.query(TrainerCatch, Pokemon)
        .join(Pokemon, TrainerCatch.pokemon_id == Pokemon.id)
        .filter(TrainerCatch.trainer_id == trainer_id)
        .order_by(TrainerCatch.caught_at.desc())
        .all()
    )
    return [
        CatchLogEntry(pokemon_id=tc.pokemon_id, name=p.name, caught_at=tc.caught_at)
        for tc, p in rows
    ]
