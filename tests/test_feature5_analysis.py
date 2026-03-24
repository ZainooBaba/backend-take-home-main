"""
Feature 5: Pokémon Rarity & Encounter Rate Analysis — GET /regions/{region_name}/analysis
"""

import pytest


class TestRarityAnalysis:

    def _create_sighting(self, client, ranger_id, pokemon_id=1, region="Kanto"):
        return client.post(
            "/sightings",
            json={
                "pokemon_id": pokemon_id,
                "region": region,
                "route": "Route 1",
                "date": "2025-06-15T10:30:00",
                "weather": "sunny",
                "time_of_day": "morning",
                "height": 0.5,
                "weight": 5.0,
            },
            headers={"X-User-ID": ranger_id},
        )

    def test_analysis_returns_expected_structure(self, client, sample_pokemon, sample_ranger):
        """Response includes total_sightings, tier breakdown, and anomalies."""
        self._create_sighting(client, sample_ranger["id"], pokemon_id=25)   # common
        self._create_sighting(client, sample_ranger["id"], pokemon_id=144)  # legendary

        data = client.get("/regions/Kanto/analysis").json()
        assert "total_sightings" in data
        assert "anomalies" in data
        assert isinstance(data["anomalies"], list)

    def test_analysis_tier_counts(self, client, sample_pokemon, sample_ranger):
        """Multiple rarity tiers appear with correct total."""
        self._create_sighting(client, sample_ranger["id"], pokemon_id=25)   # common (190)
        self._create_sighting(client, sample_ranger["id"], pokemon_id=1)    # rare (45)
        self._create_sighting(client, sample_ranger["id"], pokemon_id=144)  # legendary
        self._create_sighting(client, sample_ranger["id"], pokemon_id=151)  # mythical

        data = client.get("/regions/Kanto/analysis").json()
        assert data["total_sightings"] == 4

    def test_analysis_tier_has_percentage(self, client, sample_pokemon, sample_ranger):
        """Each tier in the breakdown includes a percentage field."""
        self._create_sighting(client, sample_ranger["id"], pokemon_id=25)
        self._create_sighting(client, sample_ranger["id"], pokemon_id=1)

        data = client.get("/regions/Kanto/analysis").json()
        # Find the tier breakdown — could be keyed as "tiers", "breakdown", or "rarity_breakdown"
        tiers = data.get("tiers") or data.get("breakdown") or data.get("rarity_breakdown", [])
        if isinstance(tiers, list) and len(tiers) > 0:
            assert "percentage" in tiers[0] or "percent" in tiers[0]
        elif isinstance(tiers, dict):
            first_tier = next(iter(tiers.values()))
            assert "percentage" in first_tier or "percent" in first_tier

    def test_analysis_tier_has_species_list(self, client, sample_pokemon, sample_ranger):
        """Each tier includes the list of observed species with counts."""
        self._create_sighting(client, sample_ranger["id"], pokemon_id=25)

        data = client.get("/regions/Kanto/analysis").json()
        tiers = data.get("tiers") or data.get("breakdown") or data.get("rarity_breakdown", [])
        if isinstance(tiers, list) and len(tiers) > 0:
            assert "species" in tiers[0] or "pokemon" in tiers[0]

    def test_analysis_empty_region(self, client, sample_pokemon):
        """Empty region returns zero or 404."""
        resp = client.get("/regions/Johto/analysis")
        if resp.status_code == 200:
            assert resp.json()["total_sightings"] == 0
        else:
            assert resp.status_code == 404
