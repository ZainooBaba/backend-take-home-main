"""Rarity tier classification shared across analysis and leaderboard features."""
from dataclasses import dataclass

TIER_ORDER = ["mythical", "legendary", "rare", "uncommon", "common"]

_TIERS = [
    # (predicate, name, numeric priority)
    (lambda m, l, cr: m,        "mythical",  5),
    (lambda m, l, cr: l,        "legendary", 4),
    (lambda m, l, cr: cr < 75,  "rare",      3),
    (lambda m, l, cr: cr < 150, "uncommon",  2),
    (lambda m, l, cr: True,     "common",    1),
]


@dataclass(frozen=True)
class RarityInfo:
    name: str
    priority: int


def rarity(is_mythical: bool, is_legendary: bool, capture_rate: int) -> RarityInfo:
    """Return name and numeric priority for a Pokémon's rarity tier."""
    for predicate, name, priority in _TIERS:
        if predicate(is_mythical, is_legendary, capture_rate):
            return RarityInfo(name=name, priority=priority)
    return RarityInfo(name="common", priority=1)  # unreachable, satisfies type checker


def rarity_tier(is_mythical: bool, is_legendary: bool, capture_rate: int) -> str:
    return rarity(is_mythical, is_legendary, capture_rate).name


def rarity_priority(is_mythical: bool, is_legendary: bool, capture_rate: int) -> int:
    return rarity(is_mythical, is_legendary, capture_rate).priority
