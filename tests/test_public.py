"""
Public test suite for the PokéTracker API.
"""

import pytest


# ============================================================
# Trainer & Ranger Registration
# ============================================================

class TestTrainerRegistration:
    def test_create_trainer(self, client):
        response = client.post("/trainers", json={
            "name": "Trainer Red",
            "email": "red@pokemon-league.org",
        })
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Trainer Red"
        assert data["email"] == "red@pokemon-league.org"
        assert "id" in data

    def test_get_trainer(self, client, sample_trainer):
        response = client.get(f"/trainers/{sample_trainer['id']}")
        assert response.status_code == 200
        assert response.json()["name"] == sample_trainer["name"]

    def test_get_trainer_not_found(self, client):
        response = client.get("/trainers/nonexistent-uuid")
        assert response.status_code == 404


class TestRangerRegistration:
    def test_create_ranger(self, client):
        response = client.post("/rangers", json={
            "name": "Ranger Ash",
            "email": "ash@pokemon-institute.org",
            "specialization": "Electric",
        })
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Ranger Ash"
        assert data["specialization"] == "Electric"
        assert "id" in data

    def test_get_ranger(self, client, sample_ranger):
        response = client.get(f"/rangers/{sample_ranger['id']}")
        assert response.status_code == 200
        assert response.json()["name"] == sample_ranger["name"]

    def test_get_ranger_not_found(self, client):
        response = client.get("/rangers/nonexistent-uuid")
        assert response.status_code == 404


# ============================================================
# User Lookup
# ============================================================

class TestUserLookup:
    def test_lookup_trainer_by_name(self, client, sample_trainer):
        response = client.get("/users/lookup", params={"name": sample_trainer["name"]})
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == sample_trainer["id"]
        assert data["role"] == "trainer"

    def test_lookup_ranger_by_name(self, client, sample_ranger):
        response = client.get("/users/lookup", params={"name": sample_ranger["name"]})
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == sample_ranger["id"]
        assert data["role"] == "ranger"

    def test_lookup_not_found(self, client):
        response = client.get("/users/lookup", params={"name": "Nobody"})
        assert response.status_code == 404


# ============================================================
# Pokédex
# ============================================================

class TestPokedex:
    def test_list_pokemon(self, client, sample_pokemon):
        response = client.get("/pokedex")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == len(sample_pokemon)

    def test_get_pokemon_by_id(self, client, sample_pokemon):
        response = client.get("/pokedex/25")
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Pikachu"
        assert data["type1"] == "Electric"

    def test_get_pokemon_not_found(self, client, sample_pokemon):
        response = client.get("/pokedex/999")
        assert response.status_code == 404

    def test_get_pokemon_by_region(self, client, sample_pokemon):
        response = client.get("/pokedex/kanto")
        assert response.status_code == 200
        data = response.json()
        # All sample Gen 1 pokemon
        assert len(data) > 0
        for p in data:
            assert p["generation"] == 1

    def test_search_pokemon(self, client, sample_pokemon):
        response = client.get("/pokedex/search", params={"name": "char"})
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1
        assert any(p["name"] == "Charmander" for p in data)


# ============================================================
# Sightings (Basic CRUD)
# ============================================================

class TestSightings:
    def test_create_sighting(self, client, sample_pokemon, sample_ranger):
        response = client.post(
            "/sightings",
            json={
                "pokemon_id": 1,
                "region": "Kanto",
                "route": "Route 1",
                "date": "2025-06-15T10:30:00",
                "weather": "sunny",
                "time_of_day": "morning",
                "height": 0.7,
                "weight": 6.9,
                "is_shiny": False,
                "notes": "Spotted in tall grass",
            },
            headers={"X-User-ID": sample_ranger["id"]},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["pokemon_id"] == 1
        assert data["region"] == "Kanto"
        assert data["ranger_id"] == sample_ranger["id"]
        assert data["is_confirmed"] is False

    def test_create_sighting_requires_ranger(self, client, sample_pokemon, sample_trainer):
        """Trainers should not be able to log sightings."""
        response = client.post(
            "/sightings",
            json={
                "pokemon_id": 1,
                "region": "Kanto",
                "route": "Route 1",
                "date": "2025-06-15T10:30:00",
                "weather": "sunny",
                "time_of_day": "morning",
                "height": 0.7,
                "weight": 6.9,
            },
            headers={"X-User-ID": sample_trainer["id"]},
        )
        assert response.status_code == 403

    def test_create_sighting_requires_auth(self, client, sample_pokemon):
        """Sightings require X-User-ID header."""
        response = client.post(
            "/sightings",
            json={
                "pokemon_id": 1,
                "region": "Kanto",
                "route": "Route 1",
                "date": "2025-06-15T10:30:00",
                "weather": "sunny",
                "time_of_day": "morning",
                "height": 0.7,
                "weight": 6.9,
            },
        )
        assert response.status_code == 401

    def test_create_sighting_invalid_weather(self, client, sample_pokemon, sample_ranger):
        response = client.post(
            "/sightings",
            json={
                "pokemon_id": 1,
                "region": "Kanto",
                "route": "Route 1",
                "date": "2025-06-15T10:30:00",
                "weather": "tornado",
                "time_of_day": "morning",
                "height": 0.7,
                "weight": 6.9,
            },
            headers={"X-User-ID": sample_ranger["id"]},
        )
        assert response.status_code == 422

    def test_get_sighting(self, client, sample_sighting):
        response = client.get(f"/sightings/{sample_sighting['id']}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == sample_sighting["id"]

    def test_get_sighting_not_found(self, client):
        response = client.get("/sightings/nonexistent-id")
        assert response.status_code == 404

    def test_delete_sighting(self, client, sample_sighting, sample_ranger):
        sighting_id = sample_sighting["id"]
        response = client.delete(
            f"/sightings/{sighting_id}",
            headers={"X-User-ID": sample_ranger["id"]},
        )
        assert response.status_code == 200

        # Verify it's gone
        response = client.get(f"/sightings/{sighting_id}")
        assert response.status_code == 404

    def test_delete_sighting_wrong_ranger(self, client, sample_sighting, second_ranger):
        """A ranger cannot delete another ranger's sighting."""
        response = client.delete(
            f"/sightings/{sample_sighting['id']}",
            headers={"X-User-ID": second_ranger["id"]},
        )
        assert response.status_code == 403


class TestRangerSightings:
    def test_get_ranger_sightings(self, client, sample_sighting, sample_ranger):
        response = client.get(f"/rangers/{sample_ranger['id']}/sightings")
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1
        assert data[0]["ranger_id"] == sample_ranger["id"]

    def test_get_ranger_sightings_not_found(self, client):
        response = client.get("/rangers/nonexistent-uuid/sightings")
        assert response.status_code == 404


# ============================================================
# Candidate-Written Tests
# ============================================================
#
# INSTRUCTIONS: Write tests for the scenarios described below.
# Each test class has a docstring explaining what you should test.
# You should write at least 2-3 tests per class.
#
# These tests factor into your evaluation — we're looking for:
# - Correct use of the test fixtures (client, sample_pokemon, etc.)
# - Coverage of both happy paths and error cases
# - Assertions that verify meaningful behavior, not just status codes
#
# You may add helper fixtures in conftest.py if needed.

class TestCandidateSightingFilters:
    """
    Write tests for the GET /sightings endpoint (Feature 1).

    Test that the endpoint supports:
    - Pagination (limit and offset query params)
    - At least two different filters (e.g., region, weather, pokemon_id)
    - Combining multiple filters narrows results correctly
    - The response includes both the page of results and the total count
    """
    pass


class TestCandidateCampaignLifecycle:
    """
    Write tests for the campaign lifecycle (Feature 2).

    Test that:
    - A campaign starts in 'draft' status
    - Transitions move the campaign forward through the lifecycle
    - A sighting can be added to an active campaign
    - A sighting CANNOT be added to a non-active campaign (draft, completed, archived)
    - Sightings tied to a completed campaign are locked (cannot be deleted)
    """
    pass


class TestCandidateConfirmation:
    """
    Write tests for the peer confirmation system (Feature 3).

    Test that:
    - A ranger can confirm another ranger's sighting
    - A ranger cannot confirm their own sighting
    - A sighting cannot be confirmed more than once
    - Only rangers (not trainers) can confirm sightings
    """
    pass
