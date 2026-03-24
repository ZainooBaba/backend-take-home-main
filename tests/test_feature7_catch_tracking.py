"""
Feature 7: Trainer Pokédex — catch tracking, summary, pokedex personalization.
"""

import pytest


class TestTrainerCatchTracking:

    # --- Mark / Unmark ---

    def test_mark_pokemon_as_caught(self, client, sample_pokemon, sample_trainer):
        """A trainer can mark a Pokémon as caught."""
        tid = sample_trainer["id"]
        resp = client.post(f"/trainers/{tid}/pokedex/25", headers={"X-User-ID": tid})
        assert resp.status_code == 200

    def test_unmark_pokemon(self, client, sample_pokemon, sample_trainer):
        """A trainer can remove a Pokémon from their catch list."""
        tid = sample_trainer["id"]
        client.post(f"/trainers/{tid}/pokedex/25", headers={"X-User-ID": tid})

        resp = client.delete(f"/trainers/{tid}/pokedex/25", headers={"X-User-ID": tid})
        assert resp.status_code == 200

    def test_duplicate_catch_is_idempotent(self, client, sample_pokemon, sample_trainer):
        """Catching the same Pokémon twice doesn't create duplicates."""
        tid = sample_trainer["id"]
        client.post(f"/trainers/{tid}/pokedex/25", headers={"X-User-ID": tid})
        resp = client.post(f"/trainers/{tid}/pokedex/25", headers={"X-User-ID": tid})
        assert resp.status_code in (200, 409)

        data = client.get(f"/trainers/{tid}/pokedex/summary").json()
        assert data["total_caught"] == 1

    def test_catch_nonexistent_pokemon(self, client, sample_pokemon, sample_trainer):
        """Catching a Pokémon ID that doesn't exist returns 404."""
        tid = sample_trainer["id"]
        resp = client.post(f"/trainers/{tid}/pokedex/9999", headers={"X-User-ID": tid})
        assert resp.status_code == 404

    # --- Authorization ---

    def test_only_owner_can_modify(self, client, sample_pokemon, sample_trainer):
        """A trainer cannot modify another trainer's catch log."""
        tid = sample_trainer["id"]
        other = client.post("/trainers", json={
            "name": "Trainer Blue", "email": "blue@pokemon-league.org",
        }).json()

        resp = client.post(f"/trainers/{tid}/pokedex/25", headers={"X-User-ID": other["id"]})
        assert resp.status_code == 403

    def test_ranger_cannot_use_catch_tracking(self, client, sample_pokemon, sample_ranger):
        """Rangers cannot use catch tracking features."""
        rid = sample_ranger["id"]
        resp = client.post(f"/trainers/{rid}/pokedex/25", headers={"X-User-ID": rid})
        assert resp.status_code in (403, 404)

    # --- Public read access ---

    def test_anyone_can_view_catch_log(self, client, sample_pokemon, sample_trainer):
        """Any user can view a trainer's public catch log."""
        tid = sample_trainer["id"]
        client.post(f"/trainers/{tid}/pokedex/25", headers={"X-User-ID": tid})

        resp = client.get(f"/trainers/{tid}/pokedex")
        assert resp.status_code == 200
        entries = resp.json() if isinstance(resp.json(), list) else resp.json().get("items", [])
        assert len(entries) >= 1

    # --- Summary ---

    def test_catch_summary(self, client, sample_pokemon, sample_trainer):
        """Summary includes total caught and completion percentage."""
        tid = sample_trainer["id"]
        client.post(f"/trainers/{tid}/pokedex/25", headers={"X-User-ID": tid})
        client.post(f"/trainers/{tid}/pokedex/1", headers={"X-User-ID": tid})

        data = client.get(f"/trainers/{tid}/pokedex/summary").json()
        assert data["total_caught"] == 2
        assert "completion_percentage" in data

    def test_catch_summary_by_type_and_generation(self, client, sample_pokemon, sample_trainer):
        """Summary includes breakdowns by type and generation."""
        tid = sample_trainer["id"]
        client.post(f"/trainers/{tid}/pokedex/25", headers={"X-User-ID": tid})   # Electric Gen1
        client.post(f"/trainers/{tid}/pokedex/152", headers={"X-User-ID": tid})  # Grass Gen2

        data = client.get(f"/trainers/{tid}/pokedex/summary").json()
        assert data["total_caught"] == 2
        assert "by_type" in data or "caught_by_type" in data
        assert "by_generation" in data or "caught_by_generation" in data

    # --- Pokédex personalization ---

    def test_pokedex_entry_shows_caught_with_header(self, client, sample_pokemon, sample_trainer):
        """GET /pokedex/{id} includes is_caught=True when trainer has caught it."""
        tid = sample_trainer["id"]
        client.post(f"/trainers/{tid}/pokedex/25", headers={"X-User-ID": tid})

        data = client.get("/pokedex/25", headers={"X-User-ID": tid}).json()
        assert data.get("is_caught") is True

    def test_pokedex_entry_shows_not_caught_with_header(self, client, sample_pokemon,
                                                         sample_trainer):
        """GET /pokedex/{id} includes is_caught=False for uncaught species."""
        tid = sample_trainer["id"]

        data = client.get("/pokedex/25", headers={"X-User-ID": tid}).json()
        assert data.get("is_caught") is False

    def test_pokedex_entry_without_header_no_caught(self, client, sample_pokemon):
        """GET /pokedex/{id} without X-User-ID header returns no caught info."""
        data = client.get("/pokedex/25").json()
        assert "is_caught" not in data or data.get("is_caught") is None
