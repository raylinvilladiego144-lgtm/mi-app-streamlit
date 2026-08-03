"""
database.py
Configuración de la sesión de base de datos SQLAlchemy para SQLite.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from base import Base

# ✅ Asegúrate de usar esta URL exacta para SQLite (3 barras para ruta relativa)
DATABASE_URL = "sqlite:///prestamos_v2.db"

engine = create_engine(
    DATABASE_URL, connect_args={"check_same_thread": False}
)

SessionLocal = sessionmaker(
    autocommit=False, autoflush=False, bind=engine
)

def init_db():
    Base.metadata.create_all(bind=engine)
