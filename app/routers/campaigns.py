from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.dependencies import get_db, require_ranger
from app.models import Campaign, Ranger, Sighting
from app.schemas import (
    CampaignCreate,
    CampaignResponse,
    CampaignSummaryResponse,
    CampaignTransition,
    CampaignUpdate,
)

router = APIRouter(tags=["Campaigns"])

VALID_TRANSITIONS = {"draft": "active", "active": "completed", "completed": "archived"}


@router.post("/campaigns", response_model=CampaignResponse, status_code=201)
def create_campaign(
    campaign: CampaignCreate,
    db: Session = Depends(get_db),
    ranger: Ranger = Depends(require_ranger),
):

    new_campaign = Campaign(
        name=campaign.name,
        description=campaign.description,
        region=campaign.region,
        start_date=campaign.start_date,
        end_date=campaign.end_date,
        created_by=ranger.id,
    )
    db.add(new_campaign)
    db.commit()
    db.refresh(new_campaign)
    return new_campaign


@router.get("/campaigns/{campaign_id}", response_model=CampaignResponse)
def get_campaign(campaign_id: str, db: Session = Depends(get_db)):
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return campaign


@router.patch("/campaigns/{campaign_id}", response_model=CampaignResponse)
def update_campaign(
    campaign_id: str,
    updates: CampaignUpdate,
    db: Session = Depends(get_db),
    ranger: Ranger = Depends(require_ranger),
):
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    if campaign.status in ("completed", "archived"):
        raise HTTPException(
            status_code=409,
            detail=f"Campaign is {campaign.status} — only status transitions are allowed",
        )

    for field, value in updates.model_dump(exclude_none=True).items():
        setattr(campaign, field, value)

    db.commit()
    db.refresh(campaign)
    return campaign


@router.post("/campaigns/{campaign_id}/transition", response_model=CampaignResponse)
def transition_campaign(
    campaign_id: str,
    body: CampaignTransition,
    db: Session = Depends(get_db),
    ranger: Ranger = Depends(require_ranger),
):
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    if VALID_TRANSITIONS.get(campaign.status) != body.status:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot transition from '{campaign.status}' to '{body.status}'",
        )

    campaign.status = body.status
    db.commit()
    db.refresh(campaign)
    return campaign


@router.get("/campaigns/{campaign_id}/summary", response_model=CampaignSummaryResponse)
def get_campaign_summary(campaign_id: str, db: Session = Depends(get_db)):
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    row = db.query(
        func.count(Sighting.id),
        func.count(Sighting.pokemon_id.distinct()),
        func.count(Sighting.ranger_id.distinct()),
        func.min(Sighting.date),
        func.max(Sighting.date),
    ).filter(Sighting.campaign_id == campaign_id).one()

    total, unique_species, contributing_rangers, earliest, latest = row
    return CampaignSummaryResponse(
        campaign_id=campaign_id,
        total_sightings=total,
        unique_species=unique_species,
        contributing_rangers=contributing_rangers,
        earliest_sighting=earliest,
        latest_sighting=latest,
    )
