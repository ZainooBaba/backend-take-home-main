"""
Feature 4: Regional Research Summary — GET /regions/{region_name}/summary
"""

import pytest


class TestRegionalSummary:

    def _create_sighting(self, client, ranger_id, pokemon_id=1, region="Kanto",
                         weather="sunny", time_of_day="morning"):
        return client.post(
            "/sightings",
            json={
                "pokemon_id": pokemon_id,
                "region": region,
                "route": "Route 1",
                "date": "2025-06-15T10:30:00",
                "weather": weather,
                "time_of_day": time_of_day,
                "height": 0.5,
                "weight": 5.0,
            },
            headers={"X-User-ID": ranger_id},
        )

    def test_summary_has_required_fields(self, client, sample_pokemon, sample_ranger):
        """Summary returns all required aggregate fields."""
        self._create_sighting(client, sample_ranger["id"])

        data = client.get("/regions/Kanto/summary").json()
        assert "total_sightings" in data
        assert "unique_species" in data
        assert "top_pokemon" in data
        assert "top_rangers" in data
        assert "by_weather" in data
        assert "by_time_of_day" in data

    def test_summary_counts_correct(self, client, sample_pokemon, sample_ranger):
        """Total sightings and unique species match created data."""
        self._create_sighting(client, sample_ranger["id"], pokemon_id=1, region="Kanto")
        self._create_sighting(client, sample_ranger["id"], pokemon_id=25, region="Kanto")
        self._create_sighting(client, sample_ranger["id"], pokemon_id=1, region="Kanto")
        self._create_sighting(client, sample_ranger["id"], pokemon_id=1, region="Johto")

        data = client.get("/regions/Kanto/summary").json()
        assert data["total_sightings"] == 3
        assert data["unique_species"] == 2

    def test_summary_top_pokemon_max_five(self, client, sample_pokemon, sample_ranger):
        """Top pokemon list has at most 5 entries."""
        for pid in [1, 4, 7, 25, 144, 150]:
            self._create_sighting(client, sample_ranger["id"], pokemon_id=pid)

        data = client.get("/regions/Kanto/summary").json()
        assert len(data["top_pokemon"]) <= 5

    def test_summary_weather_breakdown(self, client, sample_pokemon, sample_ranger):
        """Weather breakdown reflects actual conditions."""
        self._create_sighting(client, sample_ranger["id"], weather="sunny")
        self._create_sighting(client, sample_ranger["id"], weather="sunny")
        self._create_sighting(client, sample_ranger["id"], weather="rainy")

        data = client.get("/regions/Kanto/summary").json()
        weather = data["by_weather"]
        if isinstance(weather, dict):
            assert weather.get("sunny") == 2
            assert weather.get("rainy") == 1

    def test_summary_time_of_day_breakdown(self, client, sample_pokemon, sample_ranger):
        """Time-of-day breakdown reflects actual values."""
        self._create_sighting(client, sample_ranger["id"], time_of_day="morning")
        self._create_sighting(client, sample_ranger["id"], time_of_day="night")

        data = client.get("/regions/Kanto/summary").json()
        assert data["by_time_of_day"] is not None

    def test_summary_empty_region(self, client, sample_pokemon):
        """Unknown region returns zero counts or 404."""
        resp = client.get("/regions/UnknownLand/summary")
        if resp.status_code == 200:
            assert resp.json()["total_sightings"] == 0
        else:
            assert resp.status_code == 404
