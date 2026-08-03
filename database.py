"""
app/database/database.py

Configuración central de SQLAlchemy.
"""

import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from base import Base


DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:Brunoka123%2A_@db.chhccznmqdnximbaaciy.supabase.co:5432/postgres"
)


engine = create_engine(DATABASE_URL)


SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """
    Crea todas las tablas registradas en SQLAlchemy.
    """
    Base.metadata.create_all(bind=engine)
