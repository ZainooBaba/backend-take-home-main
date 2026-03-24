"""
Feature 1: Sighting Filters & Pagination — GET /sightings
"""

import pytest


class TestCandidateSightingFilters:
    """
    Test that the endpoint supports:
    - Pagination (limit and offset query params)
    - At least two different filters (e.g., region, weather, pokemon_id)
    - Combining multiple filters narrows results correctly
    - The response includes both the page of results and the total count
    """

    def _create_sighting(self, client, ranger_id, pokemon_id=1, region="Kanto",
                         weather="sunny", time_of_day="morning", date="2025-06-15T10:30:00"):
        return client.post(
            "/sightings",
            json={
                "pokemon_id": pokemon_id,
                "region": region,
                "route": "Route 1",
                "date": date,
                "weather": weather,
                "time_of_day": time_of_day,
                "height": 0.5,
                "weight": 5.0,
            },
            headers={"X-User-ID": ranger_id},
        )

    def test_response_structure_and_defaults(self, client, sample_pokemon, sample_ranger):
        """GET /sightings returns total, limit, offset, and items with sensible defaults."""
        self._create_sighting(client, sample_ranger["id"])

        data = client.get("/sightings").json()
        assert "total" in data
        assert "limit" in data
        assert "offset" in data
        assert "items" in data
        assert data["total"] >= 1
        assert data["limit"] == 20
        assert data["offset"] == 0
        assert isinstance(data["items"], list)

    def test_pagination_limit_and_offset(self, client, sample_pokemon, sample_ranger):
        """Pagination correctly limits page size and skips with offset."""
        for i in range(5):
            self._create_sighting(client, sample_ranger["id"],
                                  date=f"2025-06-{15 + i}T10:30:00")

        data1 = client.get("/sightings", params={"limit": 2, "offset": 0}).json()
        assert data1["total"] == 5
        assert len(data1["items"]) == 2

        data2 = client.get("/sightings", params={"limit": 2, "offset": 2}).json()
        assert data2["total"] == 5
        assert len(data2["items"]) == 2

        ids1 = {item["id"] for item in data1["items"]}
        ids2 = {item["id"] for item in data2["items"]}
        assert ids1.isdisjoint(ids2)

    def test_offset_past_end_returns_empty(self, client, sample_pokemon, sample_ranger):
        """Offset beyond total returns empty items but correct total."""
        self._create_sighting(client, sample_ranger["id"])

        data = client.get("/sightings", params={"limit": 10, "offset": 100}).json()
        assert data["items"] == []
        assert data["total"] == 1

    def test_filter_by_region(self, client, sample_pokemon, sample_ranger):
        """Region filter returns only sightings from that region."""
        self._create_sighting(client, sample_ranger["id"], region="Kanto")
        self._create_sighting(client, sample_ranger["id"], region="Johto")
        self._create_sighting(client, sample_ranger["id"], region="Kanto")

        data = client.get("/sightings", params={"region": "Kanto"}).json()
        assert data["total"] == 2
        for item in data["items"]:
            assert item["region"] == "Kanto"

    def test_filter_by_pokemon_id(self, client, sample_pokemon, sample_ranger):
        """pokemon_id filter returns only sightings of that species."""
        self._create_sighting(client, sample_ranger["id"], pokemon_id=1)
        self._create_sighting(client, sample_ranger["id"], pokemon_id=25)
        self._create_sighting(client, sample_ranger["id"], pokemon_id=25)

        data = client.get("/sightings", params={"pokemon_id": 25}).json()
        assert data["total"] == 2
        for item in data["items"]:
            assert item["pokemon_id"] == 25

    def test_filter_by_weather(self, client, sample_pokemon, sample_ranger):
        """Weather filter returns only matching sightings."""
        self._create_sighting(client, sample_ranger["id"], weather="sunny")
        self._create_sighting(client, sample_ranger["id"], weather="rainy")

        data = client.get("/sightings", params={"weather": "rainy"}).json()
        assert data["total"] == 1
        assert data["items"][0]["weather"] == "rainy"

    def test_combined_filters_narrow_results(self, client, sample_pokemon, sample_ranger):
        """Combining region + weather returns only the intersection."""
        self._create_sighting(client, sample_ranger["id"], region="Kanto", weather="sunny")
        self._create_sighting(client, sample_ranger["id"], region="Kanto", weather="rainy")
        self._create_sighting(client, sample_ranger["id"], region="Johto", weather="sunny")

        data = client.get("/sightings", params={"region": "Kanto", "weather": "sunny"}).json()
        assert data["total"] == 1
        assert data["items"][0]["region"] == "Kanto"
        assert data["items"][0]["weather"] == "sunny"

    def test_filter_by_date_range(self, client, sample_pokemon, sample_ranger):
        """date_from / date_to restricts results to the range."""
        self._create_sighting(client, sample_ranger["id"], date="2025-01-10T12:00:00")
        self._create_sighting(client, sample_ranger["id"], date="2025-06-15T12:00:00")
        self._create_sighting(client, sample_ranger["id"], date="2025-12-01T12:00:00")

        data = client.get("/sightings", params={
            "date_from": "2025-03-01T00:00:00",
            "date_to": "2025-09-01T00:00:00",
        }).json()
        assert data["total"] == 1

    def test_empty_result(self, client, sample_pokemon, sample_ranger):
        """Filters matching nothing return total=0 and empty items."""
        self._create_sighting(client, sample_ranger["id"], region="Kanto")

        data = client.get("/sightings", params={"region": "Johto"}).json()
        assert data["total"] == 0
        assert data["items"] == []

    def test_items_include_enriched_names(self, client, sample_pokemon, sample_ranger):
        """Each item includes pokemon_name and ranger_name."""
        self._create_sighting(client, sample_ranger["id"], pokemon_id=25)

        item = client.get("/sightings").json()["items"][0]
        assert item["pokemon_name"] == "Pikachu"
        assert item["ranger_name"] == "Ranger Ash"
