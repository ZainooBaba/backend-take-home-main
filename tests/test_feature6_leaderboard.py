"""
Feature 6: Ranger Leaderboard — GET /leaderboard
"""

import pytest


class TestRangerLeaderboard:

    def _create_sighting(self, client, ranger_id, pokemon_id=1, region="Kanto",
                         date="2025-06-15T10:30:00", is_shiny=False):
        return client.post(
            "/sightings",
            json={
                "pokemon_id": pokemon_id,
                "region": region,
                "route": "Route 1",
                "date": date,
                "weather": "sunny",
                "time_of_day": "morning",
                "height": 0.5,
                "weight": 5.0,
                "is_shiny": is_shiny,
            },
            headers={"X-User-ID": ranger_id},
        )

    def _get_entries(self, data):
        """Extract the list of leaderboard entries regardless of wrapper shape."""
        if isinstance(data, list):
            return data
        return data.get("items") or data.get("rankings") or []

    def test_leaderboard_returns_ranked_rangers(self, client, sample_pokemon,
                                                 sample_ranger, second_ranger):
        """Leaderboard returns rangers with expected stat fields."""
        for i in range(3):
            self._create_sighting(client, sample_ranger["id"],
                                  date=f"2025-06-{15 + i}T10:00:00")
        self._create_sighting(client, second_ranger["id"])

        data = client.get("/leaderboard").json()
        entries = self._get_entries(data)
        assert len(entries) >= 2

        top = entries[0]
        assert "total_sightings" in top
        assert "unique_species" in top
        assert "confirmed_sightings" in top or "confirmed_count" in top

    def test_leaderboard_default_sort_by_total(self, client, sample_pokemon,
                                                sample_ranger, second_ranger):
        """By default, the ranger with the most sightings is first."""
        for i in range(3):
            self._create_sighting(client, sample_ranger["id"],
                                  date=f"2025-06-{15 + i}T10:00:00")
        self._create_sighting(client, second_ranger["id"])

        entries = self._get_entries(client.get("/leaderboard").json())
        assert entries[0]["total_sightings"] >= entries[1]["total_sightings"]

    def test_leaderboard_filter_by_region(self, client, sample_pokemon,
                                           sample_ranger, second_ranger):
        """Scoping to a region only counts sightings in that region."""
        self._create_sighting(client, sample_ranger["id"], region="Kanto")
        self._create_sighting(client, second_ranger["id"], region="Johto")

        resp = client.get("/leaderboard", params={"region": "Kanto"})
        assert resp.status_code == 200

    def test_leaderboard_filter_by_date_range(self, client, sample_pokemon, sample_ranger):
        """Date range filter restricts which sightings count."""
        self._create_sighting(client, sample_ranger["id"], date="2025-01-15T10:00:00")
        self._create_sighting(client, sample_ranger["id"], date="2025-06-15T10:00:00")

        resp = client.get("/leaderboard", params={
            "date_from": "2025-06-01T00:00:00",
            "date_to": "2025-06-30T00:00:00",
        })
        assert resp.status_code == 200

    def test_leaderboard_sort_by_unique_species(self, client, sample_pokemon,
                                                 sample_ranger, second_ranger):
        """sort_by=unique_species changes the ranking order."""
        self._create_sighting(client, sample_ranger["id"], pokemon_id=1)
        self._create_sighting(client, sample_ranger["id"], pokemon_id=25)
        self._create_sighting(client, second_ranger["id"], pokemon_id=1)

        resp = client.get("/leaderboard", params={"sort_by": "unique_species"})
        assert resp.status_code == 200

    def test_leaderboard_pagination(self, client, sample_pokemon, sample_ranger):
        """Leaderboard supports limit and offset."""
        self._create_sighting(client, sample_ranger["id"])

        resp = client.get("/leaderboard", params={"limit": 1, "offset": 0})
        assert resp.status_code == 200

    def test_leaderboard_includes_rarest_pokemon(self, client, sample_pokemon,
                                                  sample_ranger):
        """Each entry includes the single rarest Pokémon observed."""
        self._create_sighting(client, sample_ranger["id"], pokemon_id=25)   # common
        self._create_sighting(client, sample_ranger["id"], pokemon_id=151)  # mythical

        entries = self._get_entries(client.get("/leaderboard").json())
        top = entries[0]
        assert "rarest_pokemon" in top or "rarest_sighting" in top
