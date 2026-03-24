"""Shared sighting helpers used across multiple routers."""

from app.models import Pokemon, Ranger, Sighting
from app.schemas import SightingResponse


def enrich_sighting(sighting: Sighting, pokemon: Pokemon, ranger: Ranger) -> SightingResponse:
    """Build a SightingResponse from ORM objects without extra queries."""
    resp = SightingResponse.model_validate(sighting)
    resp.pokemon_name = pokemon.name if pokemon else None
    resp.ranger_name = ranger.name if ranger else None
    return resp
