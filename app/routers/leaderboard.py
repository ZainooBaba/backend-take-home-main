from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import Integer, func
from sqlalchemy.orm import Session
from datetime import datetime
from typing import Optional

from app.dependencies import get_db
from app.models import Pokemon, Ranger, Sighting
from app.schemas import LeaderboardEntry, LeaderboardResponse, RarestPokemon
from app.services.rarity import rarity_priority, rarity_tier

router = APIRouter(tags=["Leaderboard"])

_LEADERBOARD_SORT = {
    "total_sightings": lambda: func.count(Sighting.id).desc(),
    "confirmed_sightings": lambda: func.sum(Sighting.is_confirmed.cast(Integer)).desc(),
    "unique_species": lambda: func.count(Sighting.pokemon_id.distinct()).desc(),
}


@router.get("/leaderboard", response_model=LeaderboardResponse)
def get_leaderboard(
    db: Session = Depends(get_db),
    region: Optional[str] = Query(None, description="Filter by region"),
    date_from: Optional[datetime] = Query(None, description="Start of date range (inclusive)"),
    date_to: Optional[datetime] = Query(None, description="End of date range (inclusive)"),
    campaign_id: Optional[str] = Query(None, description="Filter by campaign ID"),
    sort_by: str = Query(
        "total_sightings",
        description="Ranking field: total_sightings | confirmed_sightings | unique_species",
    ),
    limit: int = Query(20, ge=1, le=100, description="Page size"),
    offset: int = Query(0, ge=0, description="Number of records to skip"),
):
    """
    Ranked list of rangers by sighting activity.

    Aggregates total sightings, confirmed sightings, and unique species per ranger
    across the (optionally filtered) sighting set. Each entry includes the single
    rarest Pokémon that ranger has sighted within the filter scope.
    """
    if sort_by not in _LEADERBOARD_SORT:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid sort_by '{sort_by}'. Choose from: {', '.join(_LEADERBOARD_SORT)}",
        )

    filters = []
    if region is not None:
        filters.append(Sighting.region == region)
    if date_from is not None:
        filters.append(Sighting.date >= date_from)
    if date_to is not None:
        filters.append(Sighting.date <= date_to)
    if campaign_id is not None:
        filters.append(Sighting.campaign_id == campaign_id)

    total = db.query(func.count(Sighting.ranger_id.distinct())).filter(*filters).scalar() or 0

    sort_expr = _LEADERBOARD_SORT[sort_by]()
    agg_rows = (
        db.query(
            Sighting.ranger_id,
            Ranger.name.label("ranger_name"),
            func.count(Sighting.id).label("total_sightings"),
            func.sum(Sighting.is_confirmed.cast(Integer)).label("confirmed_sightings"),
            func.count(Sighting.pokemon_id.distinct()).label("unique_species"),
        )
        .join(Ranger, Sighting.ranger_id == Ranger.id)
        .filter(*filters)
        .group_by(Sighting.ranger_id, Ranger.name)
        .order_by(sort_expr)
        .offset(offset)
        .limit(limit)
        .all()
    )

    if not agg_rows:
        return LeaderboardResponse(total=total, limit=limit, offset=offset, items=[])

    ranger_ids = [row.ranger_id for row in agg_rows]

    pokemon_rows = (
        db.query(
            Sighting.ranger_id,
            Pokemon.id,
            Pokemon.name,
            Pokemon.is_mythical,
            Pokemon.is_legendary,
            Pokemon.capture_rate,
        )
        .join(Pokemon, Sighting.pokemon_id == Pokemon.id)
        .filter(Sighting.ranger_id.in_(ranger_ids), *filters)
        .distinct()
        .all()
    )

    ranger_rarest: dict[str, tuple[int, RarestPokemon]] = {}
    for row in pokemon_rows:
        priority = rarity_priority(row.is_mythical, row.is_legendary, row.capture_rate)
        existing = ranger_rarest.get(row.ranger_id)
        if existing is None or priority > existing[0]:
            tier = rarity_tier(row.is_mythical, row.is_legendary, row.capture_rate)
            ranger_rarest[row.ranger_id] = (
                priority,
                RarestPokemon(pokemon_id=row.id, name=row.name, tier=tier),
            )

    items = [
        LeaderboardEntry(
            rank=offset + i + 1,
            ranger_id=row.ranger_id,
            ranger_name=row.ranger_name,
            total_sightings=row.total_sightings,
            confirmed_sightings=row.confirmed_sightings or 0,
            unique_species=row.unique_species,
            rarest_pokemon=ranger_rarest[row.ranger_id][1] if row.ranger_id in ranger_rarest else None,
        )
        for i, row in enumerate(agg_rows)
    ]

    return LeaderboardResponse(total=total, limit=limit, offset=offset, items=items)
