"""
Feature 3: Peer Confirmation System — confirm/reject rules.
"""

import pytest


class TestCandidateConfirmation:
    """
    Test that:
    - A ranger can confirm another ranger's sighting
    - A ranger cannot confirm their own sighting
    - A sighting cannot be confirmed more than once
    - Only rangers (not trainers) can confirm sightings
    """

    def _create_sighting(self, client, ranger_id, pokemon_id=25):
        return client.post(
            "/sightings",
            json={
                "pokemon_id": pokemon_id,
                "region": "Kanto",
                "route": "Route 1",
                "date": "2025-06-15T10:30:00",
                "weather": "sunny",
                "time_of_day": "morning",
                "height": 0.4,
                "weight": 6.0,
            },
            headers={"X-User-ID": ranger_id},
        ).json()

    def test_ranger_confirms_peer_sighting(self, client, sample_pokemon,
                                            sample_ranger, second_ranger):
        """A ranger can confirm another ranger's sighting."""
        sighting = self._create_sighting(client, sample_ranger["id"])
        assert sighting["is_confirmed"] is False

        resp = client.post(
            f"/sightings/{sighting['id']}/confirm",
            headers={"X-User-ID": second_ranger["id"]},
        )
        assert resp.status_code == 200

        updated = client.get(f"/sightings/{sighting['id']}").json()
        assert updated["is_confirmed"] is True

    def test_cannot_confirm_own_sighting(self, client, sample_pokemon, sample_ranger):
        """A ranger cannot confirm their own sighting."""
        sighting = self._create_sighting(client, sample_ranger["id"])

        resp = client.post(
            f"/sightings/{sighting['id']}/confirm",
            headers={"X-User-ID": sample_ranger["id"]},
        )
        assert resp.status_code in (400, 403, 409)

    def test_cannot_confirm_twice(self, client, sample_pokemon, sample_ranger, second_ranger):
        """A sighting already confirmed cannot be confirmed again."""
        sighting = self._create_sighting(client, sample_ranger["id"])

        client.post(
            f"/sightings/{sighting['id']}/confirm",
            headers={"X-User-ID": second_ranger["id"]},
        )

        third = client.post("/rangers", json={
            "name": "Ranger Brock",
            "email": "brock@pokemon-institute.org",
            "specialization": "Rock",
        }).json()

        resp = client.post(
            f"/sightings/{sighting['id']}/confirm",
            headers={"X-User-ID": third["id"]},
        )
        assert resp.status_code in (400, 409)

    def test_trainer_cannot_confirm(self, client, sample_pokemon,
                                     sample_ranger, sample_trainer):
        """Trainers cannot confirm sightings."""
        sighting = self._create_sighting(client, sample_ranger["id"])

        resp = client.post(
            f"/sightings/{sighting['id']}/confirm",
            headers={"X-User-ID": sample_trainer["id"]},
        )
        assert resp.status_code in (400, 403)

    def test_confirm_nonexistent_sighting(self, client, sample_pokemon, second_ranger):
        """Confirming a nonexistent sighting returns 404."""
        resp = client.post(
            "/sightings/nonexistent-id/confirm",
            headers={"X-User-ID": second_ranger["id"]},
        )
        assert resp.status_code == 404

    def test_confirm_requires_auth(self, client, sample_pokemon, sample_ranger):
        """Confirmation requires X-User-ID header."""
        sighting = self._create_sighting(client, sample_ranger["id"])
        resp = client.post(f"/sightings/{sighting['id']}/confirm")
        assert resp.status_code == 401

    def test_get_confirmation_details(self, client, sample_pokemon,
                                       sample_ranger, second_ranger):
        """GET /sightings/{id}/confirmation returns confirmer and timestamp."""
        sighting = self._create_sighting(client, sample_ranger["id"])
        client.post(
            f"/sightings/{sighting['id']}/confirm",
            headers={"X-User-ID": second_ranger["id"]},
        )

        resp = client.get(f"/sightings/{sighting['id']}/confirmation")
        assert resp.status_code == 200
        data = resp.json()
        assert data["confirmed_by"] == second_ranger["id"]
        assert "confirmed_at" in data
