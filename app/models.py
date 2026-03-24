from datetime import datetime
from typing import Optional

from sqlalchemy import ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.utils import generate_uuid


class Pokemon(Base):
    __tablename__ = "pokemon"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(128))
    type1: Mapped[str]
    generation: Mapped[int]
    capture_rate: Mapped[int]
    is_legendary: Mapped[bool] = mapped_column(default=False)
    is_mythical: Mapped[bool] = mapped_column(default=False)
    is_baby: Mapped[bool] = mapped_column(default=False)
    type2: Mapped[Optional[str]] = mapped_column(default=None)
    evolution_chain_id: Mapped[Optional[int]] = mapped_column(default=None)

    __table_args__ = (
        Index("ix_pokemon_generation", "generation"),
        Index("ix_pokemon_name", "name"),
    )


class Trainer(Base):
    __tablename__ = "trainers"

    name: Mapped[str]
    email: Mapped[str]
    id: Mapped[str] = mapped_column(
        primary_key=True, init=False, default_factory=generate_uuid, insert_default=generate_uuid,
    )
    created_at: Mapped[datetime] = mapped_column(
        init=False, default_factory=datetime.utcnow, insert_default=datetime.utcnow,
    )


class Ranger(Base):
    __tablename__ = "rangers"

    name: Mapped[str]
    email: Mapped[str]
    specialization: Mapped[str]
    id: Mapped[str] = mapped_column(
        primary_key=True, init=False, default_factory=generate_uuid, insert_default=generate_uuid,
    )
    created_at: Mapped[datetime] = mapped_column(
        init=False, default_factory=datetime.utcnow, insert_default=datetime.utcnow,
    )


class Campaign(Base):
    __tablename__ = "campaigns"

    name: Mapped[str]
    description: Mapped[str] = mapped_column(Text)
    region: Mapped[str]
    start_date: Mapped[datetime]
    end_date: Mapped[datetime]
    created_by: Mapped[str] = mapped_column(ForeignKey("rangers.id"))
    status: Mapped[str] = mapped_column(String(16), default="draft")
    id: Mapped[str] = mapped_column(
        primary_key=True, init=False, default_factory=generate_uuid, insert_default=generate_uuid,
    )
    created_at: Mapped[datetime] = mapped_column(
        init=False, default_factory=datetime.utcnow, insert_default=datetime.utcnow,
    )

    __table_args__ = (
        Index("ix_campaign_status", "status"),
        Index("ix_campaign_region", "region"),
    )


class TrainerCatch(Base):
    __tablename__ = "trainer_catches"

    trainer_id: Mapped[str] = mapped_column(ForeignKey("trainers.id"), primary_key=True)
    pokemon_id: Mapped[int] = mapped_column(ForeignKey("pokemon.id"), primary_key=True)
    caught_at: Mapped[datetime] = mapped_column(
        init=False, default_factory=datetime.utcnow, insert_default=datetime.utcnow,
    )


class Sighting(Base):
    __tablename__ = "sightings"

    pokemon_id: Mapped[int] = mapped_column(ForeignKey("pokemon.id"))
    ranger_id: Mapped[str] = mapped_column(ForeignKey("rangers.id"))
    region: Mapped[str]
    route: Mapped[str]
    date: Mapped[datetime]
    weather: Mapped[str]
    time_of_day: Mapped[str]
    height: Mapped[float]
    weight: Mapped[float]
    is_shiny: Mapped[bool] = mapped_column(default=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, default=None)
    latitude: Mapped[Optional[float]] = mapped_column(default=None)
    longitude: Mapped[Optional[float]] = mapped_column(default=None)
    is_confirmed: Mapped[bool] = mapped_column(default=False)
    confirmed_by: Mapped[Optional[str]] = mapped_column(ForeignKey("rangers.id"), default=None)
    confirmed_at: Mapped[Optional[datetime]] = mapped_column(default=None)
    campaign_id: Mapped[Optional[str]] = mapped_column(ForeignKey("campaigns.id"), default=None)
    id: Mapped[str] = mapped_column(
        primary_key=True, init=False, default_factory=generate_uuid, insert_default=generate_uuid,
    )

    __table_args__ = (
        Index("ix_sighting_region", "region"),
        Index("ix_sighting_pokemon_id", "pokemon_id"),
        Index("ix_sighting_ranger_id", "ranger_id"),
        Index("ix_sighting_date", "date"),
        Index("ix_sighting_weather", "weather"),
        Index("ix_sighting_time_of_day", "time_of_day"),
        Index("ix_sighting_campaign_id", "campaign_id"),
        Index("ix_sighting_region_pokemon", "region", "pokemon_id"),
        Index("ix_sighting_region_date", "region", "date"),
    )