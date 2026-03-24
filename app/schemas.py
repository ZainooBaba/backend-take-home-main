from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import Literal, Optional


# --- Campaign ---

class CampaignCreate(BaseModel):
    name: str
    description: str
    region: str
    start_date: datetime
    end_date: datetime


class CampaignUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    region: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None


class CampaignTransition(BaseModel):
    status: Literal["active", "completed", "archived"]


class CampaignResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    description: str
    region: str
    start_date: datetime
    end_date: datetime
    status: str
    created_by: str
    created_at: datetime


class CampaignSummaryResponse(BaseModel):
    campaign_id: str
    total_sightings: int
    unique_species: int
    contributing_rangers: int
    earliest_sighting: Optional[datetime]
    latest_sighting: Optional[datetime]


# --- Rarity Analysis ---

class SpeciesCount(BaseModel):
    pokemon_id: int
    name: str
    count: int


class TierBreakdown(BaseModel):
    tier: str
    count: int
    percentage: float
    species: list[SpeciesCount]


class Anomaly(BaseModel):
    pokemon_id: int
    name: str
    tier: str
    count: int
    tier_mean: float
    z_score: float
    reason: str


class RarityAnalysisResponse(BaseModel):
    region: str
    total_sightings: int
    tiers: list[TierBreakdown]
    anomalies: list[Anomaly]


# --- Regional Summary ---

class TopEntry(BaseModel):
    id: str | int
    name: str
    count: int


class RegionalSummaryResponse(BaseModel):
    region: str
    total_sightings: int
    confirmed_sightings: int
    unconfirmed_sightings: int
    unique_species: int
    top_pokemon: list[TopEntry]
    top_rangers: list[TopEntry]
    by_weather: dict[str, int]
    by_time_of_day: dict[str, int]


# --- Confirmation ---

class ConfirmationResponse(BaseModel):
    sighting_id: str
    confirmed_by: str
    confirmed_at: datetime


# --- Trainer ---

class TrainerCreate(BaseModel):
    name: str
    email: str


class TrainerResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    email: str
    created_at: datetime


# --- Ranger ---

class RangerCreate(BaseModel):
    name: str
    email: str
    specialization: str


class RangerResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    email: str
    specialization: str
    created_at: datetime


# --- User Lookup ---

class UserLookupResponse(BaseModel):
    id: str
    name: str
    role: Literal["trainer", "ranger"]


# --- Pokemon ---

class PokemonResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    type1: str
    type2: Optional[str]
    generation: int
    is_legendary: bool
    is_mythical: bool
    is_baby: bool
    capture_rate: int
    evolution_chain_id: Optional[int]


class PokemonSearchResult(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    type1: str
    type2: Optional[str]
    generation: int


# --- Sighting ---

class SightingCreate(BaseModel):
    pokemon_id: int
    region: str
    route: str
    date: datetime
    weather: Literal["sunny", "rainy", "snowy", "sandstorm", "foggy", "clear"]
    time_of_day: Literal["morning", "day", "night"]
    height: float
    weight: float
    is_shiny: bool = False
    notes: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    campaign_id: Optional[str] = None


class SightingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    pokemon_id: int
    ranger_id: str
    region: str
    route: str
    date: datetime
    weather: str
    time_of_day: str
    height: float
    weight: float
    is_shiny: bool
    notes: Optional[str]
    is_confirmed: bool
    campaign_id: Optional[str] = None
    pokemon_name: Optional[str] = None
    ranger_name: Optional[str] = None


class PaginatedSightingsResponse(BaseModel):
    """Paginated response wrapper for the GET /sightings endpoint."""
    total: int
    limit: int
    offset: int
    items: list[SightingResponse]


# --- Generic ---

class MessageResponse(BaseModel):
    detail: str