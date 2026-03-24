from fastapi import FastAPI

from app.database import engine, Base
from app.routers import campaigns, leaderboard, pokedex, rangers, regions, sightings, trainers

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Endeavor PokéTracker", version="0.1.0")

app.include_router(trainers.router)
app.include_router(rangers.router)
app.include_router(pokedex.router)
app.include_router(campaigns.router)
app.include_router(sightings.router)
app.include_router(regions.router)
app.include_router(leaderboard.router)
