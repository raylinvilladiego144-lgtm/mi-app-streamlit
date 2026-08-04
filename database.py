"""
database.py
"""
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Si no hay variable DATABASE_URL en los secretos, usa SQLite local de forma nativa
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///prestamos_v2.db")

if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
else:
    engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True,
        pool_recycle=3600,
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    try:
        from base import Base
        Base.metadata.create_all(bind=engine)
    except Exception as e:
        print(f"Nota de base de datos: {e}")
