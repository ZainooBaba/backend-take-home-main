"""
Feature 2: Research Campaigns — lifecycle, sighting association, locking.
"""

import pytest


class TestCandidateCampaignLifecycle:
    """
    Test that:
    - A campaign starts in 'draft' status
    - Transitions move the campaign forward through the lifecycle
    - A sighting can be added to an active campaign
    - A sighting CANNOT be added to a non-active campaign (draft, completed, archived)
    - Sightings tied to a completed campaign are locked (cannot be deleted)
    """

    def _create_campaign(self, client, ranger_id, name="Test Campaign", region="Kanto"):
        return client.post(
            "/campaigns",
            json={
                "name": name,
                "description": "A test campaign",
                "region": region,
                "start_date": "2025-06-01",
                "end_date": "2025-06-30",
            },
            headers={"X-User-ID": ranger_id},
        )

    def _transition(self, client, campaign_id, target_status, ranger_id):
        return client.post(
            f"/campaigns/{campaign_id}/transition",
            json={"status": target_status},
            headers={"X-User-ID": ranger_id},
        )

    def _create_sighting(self, client, ranger_id, campaign_id=None, pokemon_id=1):
        body = {
            "pokemon_id": pokemon_id,
            "region": "Kanto",
            "route": "Route 1",
            "date": "2025-06-15T10:30:00",
            "weather": "sunny",
            "time_of_day": "morning",
            "height": 0.5,
            "weight": 5.0,
        }
        if campaign_id is not None:
            body["campaign_id"] = campaign_id
        return client.post("/sightings", json=body, headers={"X-User-ID": ranger_id})

    # --- Creation ---

    def test_campaign_starts_in_draft(self, client, sample_pokemon, sample_ranger):
        """A newly created campaign has status 'draft'."""
        resp = self._create_campaign(client, sample_ranger["id"])
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "draft"
        assert data["name"] == "Test Campaign"
        assert data["region"] == "Kanto"

    # --- Lifecycle transitions ---

    def test_full_lifecycle_forward(self, client, sample_pokemon, sample_ranger):
        """draft -> active -> completed -> archived all succeed."""
        cid = self._create_campaign(client, sample_ranger["id"]).json()["id"]
        rid = sample_ranger["id"]

        resp = self._transition(client, cid, "active", rid)
        assert resp.status_code == 200
        assert resp.json()["status"] == "active"

        resp = self._transition(client, cid, "completed", rid)
        assert resp.status_code == 200
        assert resp.json()["status"] == "completed"

        resp = self._transition(client, cid, "archived", rid)
        assert resp.status_code == 200
        assert resp.json()["status"] == "archived"

    def test_backward_transition_rejected(self, client, sample_pokemon, sample_ranger):
        """active -> draft is rejected."""
        cid = self._create_campaign(client, sample_ranger["id"]).json()["id"]
        rid = sample_ranger["id"]
        self._transition(client, cid, "active", rid)

        resp = self._transition(client, cid, "draft", rid)
        assert resp.status_code in (400, 409, 422)

    def test_skip_transition_rejected(self, client, sample_pokemon, sample_ranger):
        """draft -> completed (skipping active) is rejected."""
        cid = self._create_campaign(client, sample_ranger["id"]).json()["id"]
        rid = sample_ranger["id"]

        resp = self._transition(client, cid, "completed", rid)
        assert resp.status_code in (400, 409, 422)

    # --- Sighting association ---

    def test_sighting_added_to_active_campaign(self, client, sample_pokemon, sample_ranger):
        """A sighting can be tied to an active campaign."""
        cid = self._create_campaign(client, sample_ranger["id"]).json()["id"]
        rid = sample_ranger["id"]
        self._transition(client, cid, "active", rid)

        resp = self._create_sighting(client, rid, campaign_id=cid)
        assert resp.status_code == 200
        assert resp.json().get("campaign_id") == cid

    def test_sighting_rejected_for_draft_campaign(self, client, sample_pokemon, sample_ranger):
        """Cannot log a sighting against a draft campaign."""
        cid = self._create_campaign(client, sample_ranger["id"]).json()["id"]

        resp = self._create_sighting(client, sample_ranger["id"], campaign_id=cid)
        assert resp.status_code in (400, 409, 422)

    def test_sighting_rejected_for_completed_campaign(self, client, sample_pokemon, sample_ranger):
        """Cannot log a sighting against a completed campaign."""
        cid = self._create_campaign(client, sample_ranger["id"]).json()["id"]
        rid = sample_ranger["id"]
        self._transition(client, cid, "active", rid)
        self._transition(client, cid, "completed", rid)

        resp = self._create_sighting(client, rid, campaign_id=cid)
        assert resp.status_code in (400, 409, 422)

    def test_sighting_rejected_for_archived_campaign(self, client, sample_pokemon, sample_ranger):
        """Cannot log a sighting against an archived campaign."""
        cid = self._create_campaign(client, sample_ranger["id"]).json()["id"]
        rid = sample_ranger["id"]
        self._transition(client, cid, "active", rid)
        self._transition(client, cid, "completed", rid)
        self._transition(client, cid, "archived", rid)

        resp = self._create_sighting(client, rid, campaign_id=cid)
        assert resp.status_code in (400, 409, 422)

    # --- Locking ---

    def test_completed_campaign_locks_sightings(self, client, sample_pokemon, sample_ranger):
        """Sightings tied to a completed campaign cannot be deleted."""
        cid = self._create_campaign(client, sample_ranger["id"]).json()["id"]
        rid = sample_ranger["id"]
        self._transition(client, cid, "active", rid)
        sid = self._create_sighting(client, rid, campaign_id=cid).json()["id"]
        self._transition(client, cid, "completed", rid)

        resp = client.delete(f"/sightings/{sid}", headers={"X-User-ID": rid})
        assert resp.status_code in (400, 403, 409)

    # --- CRUD ---

    def test_get_campaign_details(self, client, sample_pokemon, sample_ranger):
        """GET /campaigns/{id} returns the campaign."""
        campaign = self._create_campaign(client, sample_ranger["id"]).json()
        resp = client.get(f"/campaigns/{campaign['id']}")
        assert resp.status_code == 200
        assert resp.json()["id"] == campaign["id"]

    def test_campaign_not_found(self, client):
        """GET /campaigns/{id} for nonexistent ID returns 404."""
        assert client.get("/campaigns/nonexistent-id").status_code == 404

    def test_campaign_summary(self, client, sample_pokemon, sample_ranger):
        """Summary includes sighting count and unique species."""
        cid = self._create_campaign(client, sample_ranger["id"]).json()["id"]
        rid = sample_ranger["id"]
        self._transition(client, cid, "active", rid)
        self._create_sighting(client, rid, campaign_id=cid, pokemon_id=1)
        self._create_sighting(client, rid, campaign_id=cid, pokemon_id=25)

        data = client.get(f"/campaigns/{cid}/summary").json()
        assert data["total_sightings"] == 2
        assert data["unique_species"] == 2
