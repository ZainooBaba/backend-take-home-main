"""
Public test suite for the PokéTracker API — existing endpoints.
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
        assert response.status_code == 201
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
        assert response.status_code == 201
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
        # Response is now paginated; check via the items list and total count
        items = data.get("items", data) if isinstance(data, dict) else data
        assert len(items) == len(sample_pokemon)

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
        assert response.status_code == 201
        data = response.json()
        assert data["pokemon_id"] == 1
        assert data["region"] == "Kanto"
        assert data["ranger_id"] == sample_ranger["id"]
        assert data["is_confirmed"] is False

    def test_create_sighting_requires_ranger(self, client, sample_pokemon, sample_trainer):
        response = client.post(
            "/sightings",
            json={
                "pokemon_id": 1, "region": "Kanto", "route": "Route 1",
                "date": "2025-06-15T10:30:00", "weather": "sunny",
                "time_of_day": "morning", "height": 0.7, "weight": 6.9,
            },
            headers={"X-User-ID": sample_trainer["id"]},
        )
        assert response.status_code == 403

    def test_create_sighting_requires_auth(self, client, sample_pokemon):
        response = client.post(
            "/sightings",
            json={
                "pokemon_id": 1, "region": "Kanto", "route": "Route 1",
                "date": "2025-06-15T10:30:00", "weather": "sunny",
                "time_of_day": "morning", "height": 0.7, "weight": 6.9,
            },
        )
        assert response.status_code == 401

    def test_create_sighting_invalid_weather(self, client, sample_pokemon, sample_ranger):
        response = client.post(
            "/sightings",
            json={
                "pokemon_id": 1, "region": "Kanto", "route": "Route 1",
                "date": "2025-06-15T10:30:00", "weather": "tornado",
                "time_of_day": "morning", "height": 0.7, "weight": 6.9,
            },
            headers={"X-User-ID": sample_ranger["id"]},
        )
        assert response.status_code == 422

    def test_get_sighting(self, client, sample_sighting):
        response = client.get(f"/sightings/{sample_sighting['id']}")
        assert response.status_code == 200
        assert response.json()["id"] == sample_sighting["id"]

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
        assert client.get(f"/sightings/{sighting_id}").status_code == 404

    def test_delete_sighting_wrong_ranger(self, client, sample_sighting, second_ranger):
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
        # Response is now paginated
        items = data.get("items", data) if isinstance(data, dict) else data
        assert len(items) >= 1
        assert items[0]["ranger_id"] == sample_ranger["id"]

    def test_get_ranger_sightings_not_found(self, client):
        response = client.get("/rangers/nonexistent-uuid/sightings")
        assert response.status_code == 404
