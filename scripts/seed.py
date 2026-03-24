"""
Seed script for the PokéTracker database.
Populates the database with Pokémon species data from data/pokedex_entries.json
and generates a large set of historical sighting records.

Usage:
    uv run python scripts/seed.py
"""

import json
import random
import uuid
import os
import sys
from datetime import datetime

# Fix import path: add project root to sys.path so `app.*` resolves
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.database import engine, SessionLocal, Base
from app.models import Pokemon, Ranger, Sighting

random.seed(42)

# Regions and their routes
REGIONS = {
    "Kanto": [
        "Route 1", "Route 2", "Route 3", "Route 4", "Route 5", "Route 6",
        "Route 7", "Route 8", "Route 9", "Route 10", "Route 11", "Route 12",
        "Route 13", "Route 14", "Route 15", "Route 16", "Route 17", "Route 18",
        "Route 19", "Route 20", "Route 21", "Route 22", "Route 23", "Route 24",
        "Route 25", "Viridian Forest", "Mt. Moon", "Rock Tunnel",
        "Pokémon Tower", "Safari Zone", "Seafoam Islands", "Pokémon Mansion",
        "Victory Road", "Cerulean Cave", "Power Plant", "Diglett's Cave",
    ],
    "Johto": [
        "Route 29", "Route 30", "Route 31", "Route 32", "Route 33",
        "Route 34", "Route 35", "Route 36", "Route 37", "Route 38",
        "Route 39", "Route 40", "Route 41", "Route 42", "Route 43",
        "Route 44", "Route 45", "Route 46", "Sprout Tower", "Ruins of Alph",
        "Union Cave", "Slowpoke Well", "Ilex Forest", "National Park",
        "Burned Tower", "Bell Tower", "Whirl Islands", "Mt. Mortar",
        "Lake of Rage", "Ice Path", "Dragon's Den", "Mt. Silver",
    ],
    "Hoenn": [
        "Route 101", "Route 102", "Route 103", "Route 104", "Route 110",
        "Route 111", "Route 112", "Route 113", "Route 114", "Route 115",
        "Route 116", "Route 117", "Route 118", "Route 119", "Route 120",
        "Route 121", "Route 122", "Route 123", "Route 124", "Route 125",
        "Route 126", "Route 127", "Route 128", "Route 129", "Route 130",
        "Route 131", "Route 132", "Route 133", "Route 134",
        "Petalburg Woods", "Rusturf Tunnel", "Granite Cave", "Meteor Falls",
        "Mt. Chimney", "Jagged Pass", "Fiery Path", "New Mauville",
        "Shoal Cave", "Mt. Pyre", "Seafloor Cavern", "Cave of Origin",
        "Victory Road", "Sky Pillar",
    ],
    "Sinnoh": [
        "Route 201", "Route 202", "Route 203", "Route 204", "Route 205",
        "Route 206", "Route 207", "Route 208", "Route 209", "Route 210",
        "Route 211", "Route 212", "Route 213", "Route 214", "Route 215",
        "Route 216", "Route 217", "Route 218", "Route 219", "Route 220",
        "Route 221", "Route 222", "Route 223", "Route 224", "Route 225",
        "Route 226", "Route 227", "Route 228", "Route 229", "Route 230",
        "Eterna Forest", "Wayward Cave", "Mt. Coronet", "Lost Tower",
        "Solaceon Ruins", "Iron Island", "Lake Verity", "Lake Valor",
        "Lake Acuity", "Stark Mountain", "Snowpoint Temple", "Turnback Cave",
    ],
}

WEATHER_OPTIONS = ["sunny", "rainy", "snowy", "sandstorm", "foggy", "clear"]
TIME_OF_DAY_OPTIONS = ["morning", "day", "night"]

POKEMON_TYPES = [
    "Normal", "Fire", "Water", "Electric", "Grass", "Ice",
    "Fighting", "Poison", "Ground", "Flying", "Psychic",
    "Bug", "Rock", "Ghost", "Dragon", "Dark", "Steel", "Fairy",
]

# Sample ranger data
RANGER_DATA = [
    {"name": "Ranger Oak", "email": "oak@pokemon-institute.org", "specialization": "Normal"},
    {"name": "Ranger Misty", "email": "misty@pokemon-institute.org", "specialization": "Water"},
    {"name": "Ranger Brock", "email": "brock@pokemon-institute.org", "specialization": "Rock"},
    {"name": "Ranger Erika", "email": "erika@pokemon-institute.org", "specialization": "Grass"},
    {"name": "Ranger Surge", "email": "surge@pokemon-institute.org", "specialization": "Electric"},
    {"name": "Ranger Sabrina", "email": "sabrina@pokemon-institute.org", "specialization": "Psychic"},
    {"name": "Ranger Blaine", "email": "blaine@pokemon-institute.org", "specialization": "Fire"},
    {"name": "Ranger Koga", "email": "koga@pokemon-institute.org", "specialization": "Poison"},
    {"name": "Ranger Giovanni", "email": "giovanni@pokemon-institute.org", "specialization": "Ground"},
    {"name": "Ranger Jasmine", "email": "jasmine@pokemon-institute.org", "specialization": "Steel"},
    {"name": "Ranger Chuck", "email": "chuck@pokemon-institute.org", "specialization": "Fighting"},
    {"name": "Ranger Pryce", "email": "pryce@pokemon-institute.org", "specialization": "Ice"},
    {"name": "Ranger Clair", "email": "clair@pokemon-institute.org", "specialization": "Dragon"},
    {"name": "Ranger Bugsy", "email": "bugsy@pokemon-institute.org", "specialization": "Bug"},
    {"name": "Ranger Morty", "email": "morty@pokemon-institute.org", "specialization": "Ghost"},
    {"name": "Ranger Whitney", "email": "whitney@pokemon-institute.org", "specialization": "Normal"},
    {"name": "Ranger Falkner", "email": "falkner@pokemon-institute.org", "specialization": "Flying"},
    {"name": "Ranger Roxanne", "email": "roxanne@pokemon-institute.org", "specialization": "Rock"},
    {"name": "Ranger Brawly", "email": "brawly@pokemon-institute.org", "specialization": "Fighting"},
    {"name": "Ranger Wattson", "email": "wattson@pokemon-institute.org", "specialization": "Electric"},
    {"name": "Ranger Flannery", "email": "flannery@pokemon-institute.org", "specialization": "Fire"},
    {"name": "Ranger Norman", "email": "norman@pokemon-institute.org", "specialization": "Normal"},
    {"name": "Ranger Winona", "email": "winona@pokemon-institute.org", "specialization": "Flying"},
    {"name": "Ranger Tate", "email": "tate@pokemon-institute.org", "specialization": "Psychic"},
    {"name": "Ranger Wallace", "email": "wallace@pokemon-institute.org", "specialization": "Water"},
    {"name": "Ranger Roark", "email": "roark@pokemon-institute.org", "specialization": "Rock"},
    {"name": "Ranger Gardenia", "email": "gardenia@pokemon-institute.org", "specialization": "Grass"},
    {"name": "Ranger Maylene", "email": "maylene@pokemon-institute.org", "specialization": "Fighting"},
    {"name": "Ranger Wake", "email": "wake@pokemon-institute.org", "specialization": "Water"},
    {"name": "Ranger Fantina", "email": "fantina@pokemon-institute.org", "specialization": "Ghost"},
    {"name": "Ranger Byron", "email": "byron@pokemon-institute.org", "specialization": "Steel"},
    {"name": "Ranger Candice", "email": "candice@pokemon-institute.org", "specialization": "Ice"},
    {"name": "Ranger Volkner", "email": "volkner@pokemon-institute.org", "specialization": "Electric"},
]

# Sample notes for sightings
SIGHTING_NOTES = [
    "Observed near tall grass",
    "Spotted during migration",
    "Very aggressive behavior",
    "Appeared docile and approachable",
    "Feeding on berries",
    "Playing with other Pokémon",
    "Seemed injured",
    "Nesting behavior observed",
    "Territorial display noted",
    "Unusually large specimen",
    "Unusually small specimen",
    "Coloring was particularly vibrant",
    "Found near water source",
    "Spotted at high altitude",
    "Cave dwelling specimen",
    "Nocturnal activity confirmed",
    None,
    None,
    None,
    None,
]


def load_pokedex_data():
    data_path = os.path.join(os.path.dirname(__file__), "..", "data", "pokedex_entries.json")
    with open(data_path) as f:
        return json.load(f)


def get_pokemon_for_region(all_pokemon, region_name):
    """Get pokemon that can appear in a region. Primarily regional pokemon but some crossover."""
    region_gen = {"Kanto": 1, "Johto": 2, "Hoenn": 3, "Sinnoh": 4}
    gen = region_gen[region_name]

    regional = [p for p in all_pokemon if p["generation"] == gen]
    others = [p for p in all_pokemon if p["generation"] != gen]

    crossover_count = max(10, len(regional) // 4)
    crossover = random.sample(others, min(crossover_count, len(others)))

    return regional + crossover


def generate_sightings(db, pokemon_data, rangers, num_sightings=55000):
    """Generate sighting records across all regions."""
    print(f"Generating {num_sightings} sighting records...")

    region_weights = {"Kanto": 0.30, "Johto": 0.25, "Hoenn": 0.25, "Sinnoh": 0.20}

    sightings = []
    for i in range(num_sightings):
        region = random.choices(
            list(region_weights.keys()),
            weights=list(region_weights.values()),
            k=1,
        )[0]

        routes = REGIONS[region]
        route = random.choice(routes)

        available_pokemon = get_pokemon_for_region(pokemon_data, region)
        pokemon = random.choice(available_pokemon)

        ranger = random.choice(rangers)

        year = random.choice([2024, 2025])
        month = random.randint(1, 12)
        day = random.randint(1, 28)
        hour = random.randint(0, 23)
        minute = random.randint(0, 59)

        sighting = Sighting(
            pokemon_id=pokemon["id"],
            ranger_id=ranger.id,
            region=region,
            route=route,
            date=datetime(year, month, day, hour, minute),
            weather=random.choice(WEATHER_OPTIONS),
            time_of_day=random.choice(TIME_OF_DAY_OPTIONS),
            height=round(random.uniform(0.1, 20.0), 2),
            weight=round(random.uniform(0.1, 999.0), 2),
            is_shiny=random.random() < 0.012,
            notes=random.choice(SIGHTING_NOTES),
            is_confirmed=random.random() < 0.3,
        )
        sightings.append(sighting)

        if (i + 1) % 10000 == 0:
            print(f"  Generated {i + 1}/{num_sightings} sightings...")

    db.bulk_save_objects(sightings)
    db.commit()
    print(f"  Inserted {len(sightings)} sighting records.")


def seed_database():
    print("=== PokéTracker Database Seeder ===")
    print()

    # Create tables
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()

    # Check if already seeded
    existing = db.query(Pokemon).count()
    if existing > 0:
        print("Database already contains data. Drop the database file to re-seed.")
        print(f"  Found {existing} Pokémon species already loaded.")
        return

    # Load Pokémon data
    print("Loading Pokémon species data...")
    pokemon_data = load_pokedex_data()
    print(f"  Found {len(pokemon_data)} species in data file.")

    # Insert Pokémon
    # Bug fix #3: "species_name" -> "name" (model field is `name`, not `species_name`)
    for entry in pokemon_data:
        pokemon = Pokemon(
            id=entry["id"],
            name=entry["name"],
            type1=entry["type1"],
            type2=entry["type2"],
            generation=entry["generation"],
            capture_rate=entry["capture_rate"],
            is_legendary=entry["is_legendary"],
            is_mythical=entry["is_mythical"],
            is_baby=entry["is_baby"],
            evolution_chain_id=entry.get("evolution_chain_id"),
        )
        db.add(pokemon)

    db.commit()
    print(f"  Loaded {len(pokemon_data)} Pokémon species.")

    # Create Rangers
    print("Creating ranger profiles...")
    rangers = []
    for rd in RANGER_DATA:
        # Bug fix #5: removed "id=str(uuid.uuid4())" — Ranger model auto-generates id (init=False)
        ranger = Ranger(
            name=rd["name"],
            email=rd["email"],
            specialization=rd["specialization"],
        )
        db.add(ranger)
        rangers.append(ranger)
    db.commit()
    print(f"  Created {len(rangers)} ranger profiles.")

    # Generate sightings
    generate_sightings(db, pokemon_data, rangers)

    # Summary
    total_pokemon = db.query(Pokemon).count()
    total_rangers = db.query(Ranger).count()
    total_sightings = db.query(Sighting).count()

    print()
    print("=== Seeding Complete ===")
    print(f"  Pokémon species: {total_pokemon}")
    print(f"  Rangers: {total_rangers}")
    print(f"  Sightings: {total_sightings}")
    print()

    db.close()


if __name__ == "__main__":
    seed_database()