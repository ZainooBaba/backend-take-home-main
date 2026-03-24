from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.dependencies import get_db
from app.models import Pokemon, Ranger, Sighting, Trainer
from app.schemas import (
    PaginatedSightingsResponse,
    RangerCreate,
    RangerResponse,
    SightingResponse,
    UserLookupResponse,
)
from app.services.sighting_service import enrich_sighting

router = APIRouter(tags=["Rangers"])


@router.post("/rangers", response_model=RangerResponse)
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


@router.get("/rangers/{ranger_id}", response_model=RangerResponse)
def get_ranger(ranger_id: str, db: Session = Depends(get_db)):
    ranger = db.query(Ranger).filter(Ranger.id == ranger_id).first()
    if not ranger:
        raise HTTPException(status_code=404, detail="Ranger not found")
    return ranger


@router.get("/rangers/{ranger_id}/sightings", response_model=PaginatedSightingsResponse)
def get_ranger_sightings(
    ranger_id: str,
    db: Session = Depends(get_db),
    limit: int = Query(20, ge=1, le=100, description="Page size"),
    offset: int = Query(0, ge=0, description="Number of records to skip"),
):
    ranger = db.query(Ranger).filter(Ranger.id == ranger_id).first()
    if not ranger:
        raise HTTPException(status_code=404, detail="Ranger not found")

    total = (
        db.query(func.count(Sighting.id))
        .filter(Sighting.ranger_id == ranger_id)
        .scalar()
    )
    rows = (
        db.query(Sighting, Pokemon)
        .join(Pokemon, Sighting.pokemon_id == Pokemon.id)
        .filter(Sighting.ranger_id == ranger_id)
        .order_by(Sighting.date.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return PaginatedSightingsResponse(
        total=total,
        limit=limit,
        offset=offset,
        items=[enrich_sighting(s, p, ranger) for s, p in rows],
    )


@router.get("/users/lookup", response_model=UserLookupResponse)
def lookup_user(name: str = Query(...), db: Session = Depends(get_db)):
    trainer = db.query(Trainer).filter(Trainer.name == name).first()
    if trainer:
        return UserLookupResponse(id=trainer.id, name=trainer.name, role="trainer")
    ranger = db.query(Ranger).filter(Ranger.name == name).first()
    if ranger:
        return UserLookupResponse(id=ranger.id, name=ranger.name, role="ranger")
    raise HTTPException(status_code=404, detail="User not found")
