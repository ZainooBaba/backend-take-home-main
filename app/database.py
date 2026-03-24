from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.orm import sessionmaker, DeclarativeBase, MappedAsDataclass

SQLALCHEMY_DATABASE_URL = "sqlite:///poketracker.db"

engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(AsyncAttrs, MappedAsDataclass, DeclarativeBase):
    pass
