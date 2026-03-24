"""Rarity tier classification shared across analysis and leaderboard features."""

TIER_ORDER = ["mythical", "legendary", "rare", "uncommon", "common"]


def rarity_tier(is_mythical: bool, is_legendary: bool, capture_rate: int) -> str:
    if is_mythical:
        return "mythical"
    if is_legendary:
        return "legendary"
    if capture_rate < 75:
        return "rare"
    if capture_rate < 150:
        return "uncommon"
    return "common"


def rarity_priority(is_mythical: bool, is_legendary: bool, capture_rate: int) -> int:
    """Numeric priority for rarity comparisons (higher = rarer)."""
    if is_mythical:
        return 5
    if is_legendary:
        return 4
    if capture_rate < 75:
        return 3
    if capture_rate < 150:
        return 2
    return 1
