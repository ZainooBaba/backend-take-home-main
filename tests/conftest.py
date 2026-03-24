import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.main import app, get_db


@pytest.fixture(scope="function")
def db_session():
    """Create a fresh in-memory database for each test."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(db_session):
    """Create a test client that uses the test database session."""
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def sample_pokemon(db_session):
    """Insert a few Pokémon species for testing."""
    from app.models import Pokemon

    pokemon_data = [
        Pokemon(id=1, name="Bulbasaur", type1="Grass", type2="Poison", generation=1,
                is_legendary=False, is_mythical=False, is_baby=False, capture_rate=45,
                evolution_chain_id=1),
        Pokemon(id=4, name="Charmander", type1="Fire", type2=None, generation=1,
                is_legendary=False, is_mythical=False, is_baby=False, capture_rate=45,
                evolution_chain_id=2),
        Pokemon(id=7, name="Squirtle", type1="Water", type2=None, generation=1,
                is_legendary=False, is_mythical=False, is_baby=False, capture_rate=45,
                evolution_chain_id=3),
        Pokemon(id=25, name="Pikachu", type1="Electric", type2=None, generation=1,
                is_legendary=False, is_mythical=False, is_baby=False, capture_rate=190,
                evolution_chain_id=10),
        Pokemon(id=144, name="Articuno", type1="Ice", type2="Flying", generation=1,
                is_legendary=True, is_mythical=False, is_baby=False, capture_rate=3,
                evolution_chain_id=73),
        Pokemon(id=150, name="Mewtwo", type1="Psychic", type2=None, generation=1,
                is_legendary=True, is_mythical=False, is_baby=False, capture_rate=3,
                evolution_chain_id=77),
        Pokemon(id=151, name="Mew", type1="Psychic", type2=None, generation=1,
                is_legendary=False, is_mythical=True, is_baby=False, capture_rate=45,
                evolution_chain_id=78),
        Pokemon(id=152, name="Chikorita", type1="Grass", type2=None, generation=2,
                is_legendary=False, is_mythical=False, is_baby=False, capture_rate=45,
                evolution_chain_id=79),
        Pokemon(id=175, name="Togepi", type1="Fairy", type2=None, generation=2,
                is_legendary=False, is_mythical=False, is_baby=True, capture_rate=190,
                evolution_chain_id=87),
    ]

    for p in pokemon_data:
        db_session.add(p)
    db_session.commit()
    return pokemon_data


@pytest.fixture
def sample_ranger(client):
    """Create a sample ranger and return the response data."""
    response = client.post("/rangers", json={
        "name": "Ranger Ash",
        "email": "ash@pokemon-institute.org",
        "specialization": "Electric",
    })
    return response.json()


@pytest.fixture
def second_ranger(client):
    """Create a second ranger for peer confirmation tests."""
    response = client.post("/rangers", json={
        "name": "Ranger Gary",
        "email": "gary@pokemon-institute.org",
        "specialization": "Water",
    })
    return response.json()


@pytest.fixture
def sample_trainer(client):
    """Create a sample trainer and return the response data."""
    response = client.post("/trainers", json={
        "name": "Trainer Red",
        "email": "red@pokemon-league.org",
    })
    return response.json()


@pytest.fixture
def sample_sighting(client, sample_pokemon, sample_ranger):
    """Create a sample sighting and return the response data."""
    response = client.post(
        "/sightings",
        json={
            "pokemon_id": 25,
            "region": "Kanto",
            "route": "Route 1",
            "date": "2025-06-15T10:30:00",
            "weather": "sunny",
            "time_of_day": "morning",
            "height": 0.4,
            "weight": 6.0,
            "is_shiny": False,
            "notes": "Spotted near Viridian City",
        },
        headers={"X-User-ID": sample_ranger["id"]},
    )
    return response.json()
