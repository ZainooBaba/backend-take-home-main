import math
from collections import defaultdict

from fastapi import APIRouter, Depends, Query
from sqlalchemy import Integer, func
from sqlalchemy.orm import Session

from app.dependencies import get_db
from app.models import Pokemon, Ranger, Sighting
from app.schemas import (
    Anomaly,
    RarityAnalysisResponse,
    RegionalSummaryResponse,
    SpeciesCount,
    TierBreakdown,
    TopEntry,
)
from app.services.rarity import TIER_ORDER, rarity_tier

router = APIRouter(tags=["Regions"])


@router.get("/regions/{region_name}/summary", response_model=RegionalSummaryResponse)
def get_regional_summary(
    region_name: str,
    db: Session = Depends(get_db),
    confirmed_only: bool = Query(False, description="When true, only include confirmed sightings"),
):
    base_filter = [Sighting.region == region_name]
    if confirmed_only:
        base_filter.append(Sighting.confirmed_by.isnot(None))

    totals = db.query(
        func.count(Sighting.id),
        func.sum(Sighting.is_confirmed.cast(Integer)),
        func.count(Sighting.pokemon_id.distinct()),
    ).filter(*base_filter).one()

    total_sightings, confirmed_count, unique_species = totals
    total_sightings = total_sightings or 0
    confirmed_count = confirmed_count or 0
    unique_species = unique_species or 0

    top_poke_rows = (
        db.query(Pokemon.id, Pokemon.name, func.count(Sighting.id).label("cnt"))
        .join(Sighting, Sighting.pokemon_id == Pokemon.id)
        .filter(*base_filter)
        .group_by(Pokemon.id, Pokemon.name)
        .order_by(func.count(Sighting.id).desc())
        .limit(5)
        .all()
    )
    top_pokemon = [TopEntry(id=r.id, name=r.name, count=r.cnt) for r in top_poke_rows]

    top_ranger_rows = (
        db.query(Ranger.id, Ranger.name, func.count(Sighting.id).label("cnt"))
        .join(Sighting, Sighting.ranger_id == Ranger.id)
        .filter(*base_filter)
        .group_by(Ranger.id, Ranger.name)
        .order_by(func.count(Sighting.id).desc())
        .limit(5)
        .all()
    )
    top_rangers = [TopEntry(id=r.id, name=r.name, count=r.cnt) for r in top_ranger_rows]

    weather_rows = (
        db.query(Sighting.weather, func.count(Sighting.id))
        .filter(*base_filter)
        .group_by(Sighting.weather)
        .all()
    )
    by_weather = {w: c for w, c in weather_rows}

    tod_rows = (
        db.query(Sighting.time_of_day, func.count(Sighting.id))
        .filter(*base_filter)
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


@router.get("/regions/{region_name}/analysis", response_model=RarityAnalysisResponse)
def get_regional_analysis(
    region_name: str,
    db: Session = Depends(get_db),
    confirmed_only: bool = Query(False, description="When true, only analyse confirmed sightings"),
):
    """
    Rarity & encounter rate analysis for a region.

    A single JOIN query retrieves all (pokemon, sighting_count) pairs for the
    region. Python then buckets by rarity tier and runs a z-score anomaly
    check within each tier (see NOTES.md for reasoning).
    """
    analysis_filter = [Sighting.region == region_name]
    if confirmed_only:
        analysis_filter.append(Sighting.confirmed_by.isnot(None))

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
        .filter(*analysis_filter)
        .group_by(Pokemon.id)
        .all()
    )

    total_sightings = sum(r.cnt for r in rows)

    tier_species: dict[str, list[SpeciesCount]] = defaultdict(list)
    for r in rows:
        tier = rarity_tier(r.is_mythical, r.is_legendary, r.capture_rate)
        tier_species[tier].append(SpeciesCount(pokemon_id=r.id, name=r.name, count=r.cnt))

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
